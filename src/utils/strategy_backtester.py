# strategy_backtester.py
from __future__ import annotations

import inspect
import traceback
from dataclasses import dataclass
from typing import Any, Optional, Literal, Union, Annotated

import pandas as pd
from pydantic import BaseModel, Field

from historical_daily_prices_helper import HistoricalDailyPricesHelper
from utils.safe_python_code_executor import SafePythonCodeExecutor


Asset = Literal["USD", "BTC"]


class HoldingState(BaseModel):
    holding_id: str
    asset: Asset
    amount: float  # asset units (USD or BTC)
    stop_loss: Optional[float] = None     # threshold unit price in USD (e.g., BTC price)
    take_profit: Optional[float] = None   # threshold unit price in USD (e.g., BTC price)


class HoldingSnapshot(BaseModel):
    holding_id: str
    asset: Asset
    amount: float
    unit_value_usd: float  # USD=1, BTC=price
    total_value_usd: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class BuyOrder(BaseModel):
    action: Literal["BUY"]
    asset: Literal["BTC"]  # currently only BTC supported for buys
    amount: float          # asset units to buy (BTC)
    stop_loss: Optional[float] = None     # threshold unit price in USD
    take_profit: Optional[float] = None   # threshold unit price in USD


class SellOrder(BaseModel):
    action: Literal["SELL"]
    holding_id: str
    amount: float  # asset units to sell (e.g., BTC units from that holding)


Order = Annotated[Union[BuyOrder, SellOrder], Field(discriminator="action")]


class BacktestResult(BaseModel):
    holdings: list[HoldingSnapshot]
    total_portfolio_usd: float
    revenue_percent: float


class StrategyBacktester:
    # Initial portfolio in USD:
    INITIAL_PORTFOLIO_USD: float = 10_000.0

    # Internal constant for the USD holding id:
    USD_HOLDING_ID: str = "USD"

    def __init__(
        self,
        prices: HistoricalDailyPricesHelper,
        executor: Optional[SafePythonCodeExecutor] = None,
    ):
        self.prices = prices
        # Prefer an explicitly provided executor; otherwise reuse helper’s.
        self._executor = executor or getattr(prices, "_executor", None) or SafePythonCodeExecutor()

        self._holdings: list[HoldingState] = []
        self._next_id = 1

    def _reset_portfolio(self) -> None:
        self._holdings = [
            HoldingState(
                holding_id=self.USD_HOLDING_ID,
                asset="USD",
                amount=float(self.INITIAL_PORTFOLIO_USD),
                stop_loss=None,
                take_profit=None,
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
        # Should never happen due to reset logic:
        raise RuntimeError("USD holding missing from portfolio state.")

    def _btc_unit_price_from_row(self, row: pd.Series) -> float:
        # Use Close for valuation and strategy execution.
        return float(row["Close"])

    def _snapshot_holdings(self, price_row: pd.Series) -> list[HoldingSnapshot]:
        btc_price = self._btc_unit_price_from_row(price_row)
        out: list[HoldingSnapshot] = []
        for h in self._holdings:
            unit = 1.0 if h.asset == "USD" else btc_price
            total = float(h.amount) * float(unit)
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

    def _snapshot_payload_for_strategy(self, price_row: pd.Series) -> list[dict[str, Any]]:
        # Strategy gets plain dicts (sandbox-friendly).
        return [s.model_dump() for s in self._snapshot_holdings(price_row)]

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
            raise ValueError("Cannot SELL the USD holding via SELL order (only BTC holdings are sellable).")

        target: Optional[HoldingState] = None
        for h in self._holdings:
            if h.holding_id == order.holding_id:
                target = h
                break

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

        # Remove empty BTC holdings:
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
        """
        Enforce stop_loss / take_profit using intraday bounds:
        - stop_loss triggers if Low <= stop_loss (sell at stop_loss)
        - take_profit triggers if High >= take_profit (sell at take_profit)
        If both could trigger, stop_loss is applied first (conservative).
        """
        low = float(day_row["Low"])
        high = float(day_row["High"])

        # Make a stable list of BTC holdings to evaluate (since selling mutates self._holdings):
        btc_holdings = [h for h in self._holdings if h.asset == "BTC"]

        for h in btc_holdings:
            # Holding might have been removed by earlier trigger:
            still_present = any(x.holding_id == h.holding_id for x in self._holdings)
            if not still_present:
                continue

            if h.stop_loss is not None and low <= float(h.stop_loss):
                # Sell full amount at stop_loss price:
                self._apply_sell(
                    SellOrder(action="SELL", holding_id=h.holding_id, amount=float(h.amount)),
                    execution_price=float(h.stop_loss),
                )
                continue

            # Re-check presence after potential mutation:
            still_present = any(x.holding_id == h.holding_id for x in self._holdings)
            if not still_present:
                continue

            if h.take_profit is not None and high >= float(h.take_profit):
                self._apply_sell(
                    SellOrder(action="SELL", holding_id=h.holding_id, amount=float(h.amount)),
                    execution_price=float(h.take_profit),
                )

    def test_strategy(self, start_date, end_date, trading_strategy_code: str) -> BacktestResult | str:
        """
        Runs a daily backtest over actual dataset trading dates from start_date to end_date inclusive.

        Strategy execution (per trading day):
        1) Apply stop_loss / take_profit auto-sells using Low/High thresholds.
        2) Provide df subset up to current day and current holdings snapshot to run(df, holdings).
        3) Execute returned orders in-order at Close price for that day.

        Returns:
          - BacktestResult on success
          - error string (with stack trace) on any code execution error
          - descriptive error string on any order/validation error
        """
        try:
            dates = self.prices.get_trading_dates(start_date, end_date)
        except Exception as e:
            return f"Date range validation error: {e}"

        self._reset_portfolio()

        try:
            runner = self._compile_and_get_run(trading_strategy_code)
        except Exception as e:
            return f"Strategy code validation error: {e}"

        try:
            for day in dates:
                day_df = self.prices.get_df_until_date(day)
                day_row = self.prices.df.loc[day]  # exists since day is a trading date
                close_price = self._btc_unit_price_from_row(day_row)

                # 1) Apply stop/take triggers before strategy runs.
                self._auto_close_on_thresholds(day_row)

                # 2) Run strategy
                holdings_payload = self._snapshot_payload_for_strategy(day_row)

                try:
                    raw_orders = runner(day_df.copy(), holdings_payload)
                except Exception:
                    return (
                        "Strategy execution error (stack trace follows):\n"
                        + traceback.format_exc()
                    )

                if raw_orders is None:
                    raw_orders = []
                if not isinstance(raw_orders, list):
                    return "Order error: run(df, holdings) must return a list of orders (or an empty list)."

                # 3) Validate + apply orders in-order
                orders: list[Order] = []
                try:
                    for item in raw_orders:
                        orders.append(Order.__get_pydantic_core_schema__)  # type: ignore[attr-defined]
                except Exception:
                    # Fallback: normal validation loop (works in Pydantic v2)
                    try:
                        orders = [Order.model_validate(item) for item in raw_orders]  # type: ignore[attr-defined]
                    except Exception as e:
                        return f"Order error: invalid order payload(s): {e}"

                try:
                    self._apply_orders(orders, execution_price=close_price)
                except Exception as e:
                    return f"Order error: {e}"

            # Final valuation uses last day close:
            last_day = dates[-1]
            last_row = self.prices.df.loc[last_day]
            snapshots = self._snapshot_holdings(last_row)

            total_usd = float(sum(h.total_value_usd for h in snapshots))
            revenue_percent = ((total_usd / float(self.INITIAL_PORTFOLIO_USD)) - 1.0) * 100.0

            return BacktestResult(
                holdings=snapshots,
                total_portfolio_usd=total_usd,
                revenue_percent=revenue_percent,
            )

        except Exception:
            return "Unexpected backtest error (stack trace follows):\n" + traceback.format_exc()
