# strategy_backtester.py
from __future__ import annotations

import inspect
import traceback
from typing import Any, Optional, Literal, Union, Annotated
import pandas as pd
from pydantic import BaseModel, Field, TypeAdapter
from utils.historical_daily_prices_helper import HistoricalDailyPricesHelper
from utils.safe_python_code_executor import SafePythonCodeExecutor

Asset = Literal["USD", "BTC"]


# --- Pydantic types ---

class HoldingState(BaseModel):
    holding_id: str
    asset: Asset
    amount: float  # asset units
    stop_loss: Optional[float] = None     # unit price in USD
    take_profit: Optional[float] = None   # unit price in USD


class HoldingSnapshot(BaseModel):
    holding_id: str
    asset: Asset
    amount: float
    unit_value_usd: float  # USD=1, BTC=last known price (for strategy) / close (for final valuation)
    total_value_usd: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class BuyOrder(BaseModel):
    action: Literal["BUY"]
    asset: Literal["BTC"]
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
    ):
        self.prices = prices
        self._executor = executor or getattr(prices, "_executor", None) or SafePythonCodeExecutor()

        self._holdings: list[HoldingState] = []
        self._next_id = 1

    # -------- Portfolio bookkeeping --------

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

    # -------- Pricing helpers --------

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
        # With warm-up validation, day_df must be non-empty.
        return float(day_df["Close"].iloc[-1])

    def _snapshot_holdings_with_price(self, btc_price: float) -> list[HoldingSnapshot]:
        out: list[HoldingSnapshot] = []
        for h in self._holdings:
            unit = 1.0 if h.asset == "USD" else float(btc_price)
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

    def _strategy_holdings_payload(self, last_known_btc_price: float) -> list[dict[str, Any]]:
        # Strategy sees holdings valued at last known close (no look-ahead).
        return [s.model_dump() for s in self._snapshot_holdings_with_price(last_known_btc_price)]

    # -------- Strategy code loading --------

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

    # -------- Order application --------

    def _apply_buy(self, order: BuyOrder, execution_price: float) -> None:
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
                asset="BTC",
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
        if target.asset != "BTC":
            raise ValueError(f"SELL holding must be BTC; got {target.asset!r}.")

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

    # -------- Stop loss / take profit --------

    def _auto_close_on_thresholds(self, day_row: pd.Series) -> None:
        """
        Intraday enforcement (after orders executed at Open):
        - stop_loss triggers if Low <= stop_loss  -> sell full at stop_loss price
        - take_profit triggers if High >= take_profit -> sell full at take_profit price
        If both could trigger same day, stop_loss is applied first.
        """
        low = self._row_low(day_row)
        high = self._row_high(day_row)

        btc_holdings = [h for h in self._holdings if h.asset == "BTC" and h.amount > 1e-12]

        for h in btc_holdings:
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

    # -------- Main backtest --------

    def test_strategy(self, start_date, end_date, trading_strategy_code: str) -> BacktestResult | str:
        """
        For each trading day D in [start..end]:
          - Strategy input df = prices up to (D - 1 day) inclusive (no look-ahead)
          - Orders execute at D Open
          - stop_loss/take_profit may trigger using D Low/High (after orders)

        Warm-up requirement:
          - start_date must have at least one prior candle available to the strategy.
        """
        try:
            dates = self.prices.get_trading_dates(start_date, end_date)
        except Exception as e:
            return f"Date range validation error: {e}"

        # Warm-up validation: the first execution day must have at least 1 prior candle
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

                # No look-ahead: only past data visible
                as_of = day - pd.Timedelta(days=1)
                day_df = self.prices.get_df_until_date(as_of)
                if day_df.empty:
                    return (
                        f"Date range validation error: not enough history before {day.date()} "
                        "(warm-up)."
                    )

                last_known_btc = self._last_known_close(day_df)

                # Simulation-only (strategy never sees this row)
                day_row = self.prices.df.loc[day]
                open_price = self._row_open(day_row)

                holdings_payload = self._strategy_holdings_payload(last_known_btc)

                # Run strategy
                try:
                    raw_orders = runner(day_df.copy(), holdings_payload)
                except Exception:
                    return "Strategy execution error (stack trace follows):\n" + traceback.format_exc()

                if raw_orders is None:
                    raw_orders = []
                if not isinstance(raw_orders, list):
                    return "Order error: run(df, holdings) must return a list of orders (or an empty list)."

                # Validate orders
                try:
                    orders = OrdersAdapter.validate_python(raw_orders)
                except Exception as e:
                    return f"Order error: invalid order payload(s): {e}"

                # Apply orders at Open
                try:
                    self._apply_orders(orders, execution_price=open_price)
                except Exception as e:
                    return f"Order error: {e}"

                # Apply stop-loss / take-profit intraday
                try:
                    self._auto_close_on_thresholds(day_row)
                except Exception as e:
                    return f"Order error: {e}"

            # Final valuation at end day Close
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
