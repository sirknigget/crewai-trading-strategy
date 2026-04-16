from __future__ import annotations

from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from utils.strategy_backtester import StrategyBacktester

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
    Run a daily backtest using StrategyBacktester.
    Returns a JSON string containing BacktestResult on success, or an error string.
    """

    name: str = "Run Strategy Backtest"
    description: str = "Run a strategy backtest."
    args_schema: Type[BaseModel] = RunBacktestInput

    backtester: StrategyBacktester

    def model_post_init(self, __context) -> None:
        self.description = (
            "Runs the StrategyBacktester over a fixed start/end date window and returns "
            "the backtest result (JSON) or an error message. "
            f"The fixed backtest window is {START_DATE} to {END_DATE}. "
            f"The loaded dataset range is {self.backtester.prices.dataset_start_date} to "
            f"{self.backtester.prices.dataset_end_date}."
        )

    def _run(self, trading_strategy_code: str) -> str:
        result = self.backtester.test_strategy(
            start_date=START_DATE,
            end_date=END_DATE,
            trading_strategy_code=trading_strategy_code,
        )

        if isinstance(result, str):
            return result

        return result.model_dump_json(indent=2)
