from __future__ import annotations

from typing import  Type
from pydantic import BaseModel, Field

from crewai.tools import BaseTool
from utils.strategy_backtester import StrategyBacktester

# Backtest window constants
START_DATE: str = "2021-01-01"
END_DATE: str = "2021-01-30"

class RunBacktestInput(BaseModel):
    """Input schema for running a strategy backtest."""
    trading_strategy_code: str = Field(
        ...,
        description=(
            "Python code that defines a top-level function run(df, holdings) "
            "and returns a list of orders."
        ),
        min_length=1,
    )


class RunStrategyBacktestTool(BaseTool):
    """
    Run a BTC/USD daily backtest using StrategyBacktester.
    - Returns a JSON string containing BacktestResult on success, or an error string.

    class BacktestResult(BaseModel):
        holdings: list[HoldingSnapshot]
        total_portfolio_usd: float
        revenue_percent: float
    """

    name: str = "Run BTC Strategy Backtest"
    description: str = (
        "Runs the StrategyBacktester over a fixed start/end date window and returns "
        "the backtest result (JSON) or an error message."
    )
    args_schema: Type[BaseModel] = RunBacktestInput

    # Instance of the helper class (passed during initialization)
    backtester: StrategyBacktester

    def _run(self, trading_strategy_code: str) -> str:
        result = self._backtester.test_strategy(
            start_date=START_DATE,
            end_date=END_DATE,
            trading_strategy_code=trading_strategy_code,
        )

        # test_strategy returns BacktestResult | str
        if isinstance(result, str):
            return result

        # BacktestResult is a Pydantic model
        return result.model_dump_json(indent=2)
