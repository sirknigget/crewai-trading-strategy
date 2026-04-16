from __future__ import annotations

import inspect
import traceback
from typing import Any, Optional, Literal, Union, Annotated

import pandas as pd
from pydantic import BaseModel, Field, TypeAdapter

from utils.historical_daily_prices_helper import HistoricalDailyPricesHelper
from utils.safe_python_code_executor import SafePythonCodeExecutor

Asset = str


class HoldingState(BaseModel):
    holding_id: str
    asset: Asset
    amount: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class HoldingSnapshot(BaseModel):
    holding_id: str
    asset: Asset
    amount: float
    unit_value_usd: float
    total_value_usd: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class BuyOrder(BaseModel):
    action: Literal["BUY"]
    asset: str
    amount: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class SellOrder(BaseModel):
    action: Literal["SELL"]
    holding_id: str
    amount: float


Order = Annotated[Union[BuyOrder, SellOrder], Field(discriminator="action")]
OrdersAdapter = TypeAdapter(list[Order])


class BacktestResult(BaseModel):
    holdings: list[HoldingSnapshot]
    total_portfolio_usd: float
    revenue_percent: float


class StrategyBacktester:
    INITIAL_PORTFOLIO_USD: float = 10_000.0
    USD_HOLDING_ID: str = "USD"

    def __init__(
        self,
        prices: HistoricalDailyPricesHelper,
        executor: Optional[SafePythonCodeExecutor] = None,
        asset_symbol: str = "ASSET",
    ):
        self.prices = prices
        self.asset_symbol = asset_symbol
        self._executor = executor or getattr(prices, "_executor", None) or SafePythonCodeExecutor()

        self._holdings: list[HoldingState] = []
        self._next_id = 1

    def _reset_portfolio(self) -> None:
        self._holdings = [
            HoldingState(
                holding_id=self.USD_HOLDING_ID,
                asset="USD",
                amount=float(self.INITIAL_PORTFOLIO_USD),
            )
        ]
        self._next_id = 1

    def _new_holding_id(self) -> str:
        hid = f"H{self._next_id}"
        self._next_id += 1
        return hid

    def _get_usd_holding(self) -> HoldingState:
        for h in self._holdings:
            if h.asset == "USD":
                return h
        raise RuntimeError("USD holding missing from portfolio state.")

    def _find_holding(self, holding_id: str) -> Optional[HoldingState]:
        for h in self._holdings:
            if h.holding_id == holding_id:
                return h
        return None

    @staticmethod
    def _row_open(row: pd.Series) -> float:
        return float(row["Open"])

    @staticmethod
    def _row_high(row: pd.Series) -> float:
        return float(row["High"])

    @staticmethod
    def _row_low(row: pd.Series) -> float:
        return float(row["Low"])

    @staticmethod
    def _row_close(row: pd.Series) -> float:
        return float(row["Close"])

    @staticmethod
    def _last_known_close(day_df: pd.DataFrame) -> float:
        return float(day_df["Close"].iloc[-1])

    def _snapshot_holdings_with_price(self, asset_price: float) -> list[HoldingSnapshot]:
        out: list[HoldingSnapshot] = []
        for h in self._holdings:
            unit = 1.0 if h.asset == "USD" else float(asset_price)
            total = float(h.amount) * unit
            out.append(
                HoldingSnapshot(
                    holding_id=h.holding_id,
                    asset=h.asset,
                    amount=float(h.amount),
                    unit_value_usd=float(unit),
                    total_value_usd=float(total),
                    stop_loss=h.stop_loss,
                    take_profit=h.take_profit,
                )
            )
        return out

    def _strategy_holdings_payload(self, last_known_asset_price: float) -> list[dict[str, Any]]:
        return [
            snapshot.model_dump()
            for snapshot in self._snapshot_holdings_with_price(last_known_asset_price)
        ]

    def _compile_and_get_run(self, code: str):
        compiled = self._executor.check_and_compile(code)
        ns = self._executor.execute_compiled(compiled)

        runner = ns.get("run")
        if not callable(runner):
            raise ValueError("trading_strategy_code must define a top-level function named run(df, holdings).")

        sig = inspect.signature(runner)
        params = list(sig.parameters.values())
        if len(params) != 2:
            raise ValueError(f"run must accept exactly 2 arguments (df, holdings), found {len(params)}.")

        for p in params:
            if p.kind not in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                raise ValueError("run(df, holdings) must take both arguments positionally.")

        return runner

    def _apply_buy(self, order: BuyOrder, execution_price: float) -> None:
        if order.asset != self.asset_symbol:
            raise ValueError(
                f"BUY asset must be {self.asset_symbol!r}; got {order.asset!r}."
            )
        if order.amount <= 0:
            raise ValueError("BUY amount must be > 0.")

        usd = self._get_usd_holding()
        cost = float(order.amount) * float(execution_price)

        if cost > usd.amount + 1e-12:
            raise ValueError(
                f"Insufficient USD for BUY: required {cost:.8f}, available {usd.amount:.8f}."
            )

        usd.amount -= cost
        self._holdings.append(
            HoldingState(
                holding_id=self._new_holding_id(),
                asset=self.asset_symbol,
                amount=float(order.amount),
                stop_loss=order.stop_loss,
                take_profit=order.take_profit,
            )
        )

    def _apply_sell(self, order: SellOrder, execution_price: float) -> None:
        if order.amount <= 0:
            raise ValueError("SELL amount must be > 0.")
        if order.holding_id == self.USD_HOLDING_ID:
            raise ValueError("Cannot SELL the USD holding via SELL order.")

        target = self._find_holding(order.holding_id)
        if target is None:
            raise ValueError(f"SELL refers to non-existing holding_id={order.holding_id!r}.")
        if target.asset != self.asset_symbol:
            raise ValueError(
                f"SELL holding must be {self.asset_symbol}; got {target.asset!r}."
            )

        if order.amount > target.amount + 1e-12:
            raise ValueError(
                f"Cannot SELL more than holding contains: requested {order.amount:.8f}, available {target.amount:.8f}."
            )

        proceeds = float(order.amount) * float(execution_price)
        target.amount -= float(order.amount)

        usd = self._get_usd_holding()
        usd.amount += proceeds

        if target.amount <= 1e-12:
            self._holdings = [h for h in self._holdings if h.holding_id != target.holding_id]

    def _apply_orders(self, orders: list[Order], execution_price: float) -> None:
        for o in orders:
            if isinstance(o, BuyOrder):
                self._apply_buy(o, execution_price=execution_price)
            elif isinstance(o, SellOrder):
                self._apply_sell(o, execution_price=execution_price)
            else:
                raise ValueError(f"Unsupported order type: {type(o)}")

    def _auto_close_on_thresholds(self, day_row: pd.Series) -> None:
        low = self._row_low(day_row)
        high = self._row_high(day_row)

        asset_holdings = [
            h for h in self._holdings if h.asset == self.asset_symbol and h.amount > 1e-12
        ]

        for h in asset_holdings:
            if self._find_holding(h.holding_id) is None:
                continue

            if h.stop_loss is not None and low <= float(h.stop_loss):
                self._apply_sell(
                    SellOrder(action="SELL", holding_id=h.holding_id, amount=float(h.amount)),
                    execution_price=float(h.stop_loss),
                )
                continue

            if self._find_holding(h.holding_id) is None:
                continue

            if h.take_profit is not None and high >= float(h.take_profit):
                self._apply_sell(
                    SellOrder(action="SELL", holding_id=h.holding_id, amount=float(h.amount)),
                    execution_price=float(h.take_profit),
                )

    def test_strategy(self, start_date, end_date, trading_strategy_code: str) -> BacktestResult | str:
        try:
            dates = self.prices.get_trading_dates(start_date, end_date)
        except Exception as e:
            return f"Date range validation error: {e}"

        first_day = pd.Timestamp(dates[0]).normalize()
        as_of_first = first_day - pd.Timedelta(days=1)
        warmup_df = self.prices.get_df_until_date(as_of_first)
        if warmup_df.empty:
            return (
                "Date range validation error: start_date requires at least 1 prior candle "
                "(warm-up). Choose a later start_date."
            )

        self._reset_portfolio()

        try:
            runner = self._compile_and_get_run(trading_strategy_code)
        except Exception as e:
            return f"Strategy code validation error: {e}"

        try:
            for day in dates:
                day = pd.Timestamp(day).normalize()
                as_of = day - pd.Timedelta(days=1)
                day_df = self.prices.get_df_until_date(as_of)
                if day_df.empty:
                    return (
                        f"Date range validation error: not enough history before {day.date()} "
                        "(warm-up)."
                    )

                last_known_asset_price = self._last_known_close(day_df)
                day_row = self.prices.df.loc[day]
                holdings_payload = self._strategy_holdings_payload(last_known_asset_price)

                try:
                    raw_orders = runner(day_df.copy(), holdings_payload)
                except Exception:
                    return "Strategy execution error (stack trace follows):\n" + traceback.format_exc()

                if raw_orders is None:
                    raw_orders = []
                if not isinstance(raw_orders, list):
                    return "Order error: run(df, holdings) must return a list of orders (or an empty list)."

                try:
                    orders = OrdersAdapter.validate_python(raw_orders)
                except Exception as e:
                    return f"Order error: invalid order payload(s): {e}"

                try:
                    self._apply_orders(orders, execution_price=last_known_asset_price)
                except Exception as e:
                    return f"Order error: {e}"

                try:
                    self._auto_close_on_thresholds(day_row)
                except Exception as e:
                    return f"Order error: {e}"

            last_day = pd.Timestamp(dates[-1]).normalize()
            last_row = self.prices.df.loc[last_day]
            close_price = self._row_close(last_row)

            snapshots = self._snapshot_holdings_with_price(close_price)
            total_usd = float(sum(h.total_value_usd for h in snapshots))
            revenue_percent = ((total_usd / float(self.INITIAL_PORTFOLIO_USD)) - 1.0) * 100.0

            return BacktestResult(
                holdings=snapshots,
                total_portfolio_usd=total_usd,
                revenue_percent=revenue_percent,
            )

        except Exception:
            return "Unexpected backtest error (stack trace follows):\n" + traceback.format_exc()
