#!/usr/bin/env python
import argparse
from datetime import timedelta
from pathlib import Path

from crewai.flow import Flow, listen, or_, router, start
from pydantic import BaseModel, Field

from crewai_trading_strategy.constants import DEFAULT_ASSET_SYMBOL, DEFAULT_DATASET_PATH
from crewai_trading_strategy.crews.trading_strategy_crew.trading_strategy_crew import (
    TradingStrategyCrew,
)
from crewai_trading_strategy.strategy_code_guidelines import get_strategy_code_guidelines
from utils.code_utils import strip_llm_formatting
from utils.date_utils import parse_yyyy_mm_dd
from utils.historical_daily_prices_helper import HistoricalDailyPricesHelper
from utils.json_utils import dump_object
from utils.strategy_backtester import BacktestResult, StrategyBacktester

MAX_ATTEMPTS = 3


class TradingStrategyAttempt(BaseModel):
    strategy_outline: str
    strategy_design: str
    strategy_implementation: str
    backtest_result: BacktestResult


class TradingStrategyCreationState(BaseModel):
    attempts_log: list[TradingStrategyAttempt] = Field(default_factory=list)


class TradingStrategyCreationFlow(Flow[TradingStrategyCreationState]):
    def __init__(self, dataset_path: str = DEFAULT_DATASET_PATH, asset_symbol: str = DEFAULT_ASSET_SYMBOL):
        self.dataset_path = dataset_path
        self.asset_symbol = asset_symbol
        self.historical_price_helper = HistoricalDailyPricesHelper(csv_path=dataset_path)
        self.backtester = StrategyBacktester(
            prices=self.historical_price_helper,
            asset_symbol=asset_symbol,
        )
        super().__init__()

    def _build_inputs(self) -> dict:
        return {
            "asset_symbol": self.asset_symbol,
            "dataset_path": self.dataset_path,
            "dataset_start_date": self.historical_price_helper.dataset_start_date,
            "dataset_end_date": self.historical_price_helper.dataset_end_date,
            "strategy_code_guidelines": get_strategy_code_guidelines(
                asset_symbol=self.asset_symbol
            ),
        }

    def create_previous_attempts_info(self) -> str:
        if len(self.state.attempts_log) == 0:
            return "This is the first attempt to create the trading strategy."

        info = "Examine the previous attempts to create the trading strategy and build upon them to improve:\n"
        info += f"Previous {len(self.state.attempts_log)} attempts to create the trading strategy:\n"
        for i, attempt in enumerate(self.state.attempts_log, start=1):
            info += f"\n--- Attempt {i} ---\n"
            info += f"Strategy Outline:\n{attempt.strategy_outline}\n"
            info += f"Strategy Implementation:\n{attempt.strategy_implementation}\n"
            info += f"Backtest Result:\n{dump_object(attempt.backtest_result)}\n"
        return info

    def backtest_strategy(self, implementation_code: str) -> BacktestResult:
        print("\n\n=== STRATEGY CODE TO BACKTEST ===\n\n")
        print(implementation_code)

        start_date = parse_yyyy_mm_dd(self.historical_price_helper.dataset_start_date) + timedelta(days=1)
        end_date = parse_yyyy_mm_dd(self.historical_price_helper.dataset_end_date)
        result = self.backtester.test_strategy(start_date, end_date, implementation_code)

        print("\n\n=== BACKTEST RESULT ===\n\n")
        print(dump_object(result))

        if isinstance(result, str):
            raise ValueError(result)
        return result

    def handle_crew_output(self, crew_output) -> TradingStrategyAttempt:
        def find_task(task_name: str):
            return next((t for t in crew_output.tasks_output if t.name == task_name), None)

        research_strategy_task = find_task("research_strategy_task")
        strategy_outline = research_strategy_task.raw if research_strategy_task else ""

        design_strategy_task = find_task("design_strategy_task")
        strategy_design = design_strategy_task.raw if design_strategy_task else ""

        implementation_task = find_task("implement_strategy_task")
        implementation = implementation_task.pydantic.implementation if implementation_task else ""
        strategy_implementation = strip_llm_formatting(implementation)

        backtest_result = self.backtest_strategy(strategy_implementation)

        return TradingStrategyAttempt(
            strategy_outline=strategy_outline,
            strategy_design=strategy_design,
            strategy_implementation=strategy_implementation,
            backtest_result=backtest_result,
        )

    @start()
    def start(self) -> TradingStrategyCreationState:
        print("Starting Trading Strategy Creation Flow")
        self.state.attempts_log = []
        return self.state

    @router(or_("start", "continue"))
    def main_loop(self) -> str:
        print(f"\n\n=== ATTEMPT {len(self.state.attempts_log) + 1} TO CREATE TRADING STRATEGY ===\n\n")

        inputs = self._build_inputs()
        inputs["previous_attempts_info"] = self.create_previous_attempts_info()

        crew_output = TradingStrategyCrew(
            historical_price_helper=self.historical_price_helper,
            backtester=self.backtester,
        ).crew().kickoff(inputs=inputs)

        attempt_log = self.handle_crew_output(crew_output)
        self.state.attempts_log.append(attempt_log)

        if len(self.state.attempts_log) >= MAX_ATTEMPTS:
            return "break"
        return "continue"

    @listen("break")
    def finish(self):
        print("\n\n=== TRADING STRATEGY CREATION FLOW FINISHED ===\n\n")

        best_attempt = max(
            self.state.attempts_log,
            key=lambda attempt: attempt.backtest_result.revenue_percent,
        )
        print("Best Attempt Backtest Result:")
        print(dump_object(best_attempt.backtest_result))
        print("\nBest Attempt Strategy Implementation Code:")
        print(best_attempt.strategy_implementation)

        with open("output/trading_strategy_outline.md", "w") as f:
            f.write(best_attempt.strategy_outline)

        with open("output/trading_strategy_design.md", "w") as f:
            f.write(best_attempt.strategy_design)

        with open("output/trading_strategy_implementation.py", "w") as f:
            f.write(best_attempt.strategy_implementation)

        with open("output/trading_strategy_creation_attempts_log.json", "w") as f:
            f.write(dump_object(self.state.attempts_log))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset-path",
        default=DEFAULT_DATASET_PATH,
        help="Path to a CSV dataset with Date, Open, High, Low, Close, Volume columns.",
    )
    parser.add_argument(
        "--asset-symbol",
        default=DEFAULT_ASSET_SYMBOL,
        help="Tradable asset symbol exposed to the strategy and prompts.",
    )
    return parser.parse_args()


def kickoff(dataset_path: str | None = None, asset_symbol: str | None = None):
    if dataset_path is None or asset_symbol is None:
        args = parse_args()
        dataset_path = dataset_path or args.dataset_path
        asset_symbol = asset_symbol or args.asset_symbol

    resolved_dataset_path = str(Path(dataset_path))
    flow = TradingStrategyCreationFlow(
        dataset_path=resolved_dataset_path,
        asset_symbol=asset_symbol,
    )
    flow.kickoff()


def plot(dataset_path: str | None = None, asset_symbol: str | None = None):
    if dataset_path is None or asset_symbol is None:
        args = parse_args()
        dataset_path = dataset_path or args.dataset_path
        asset_symbol = asset_symbol or args.asset_symbol

    resolved_dataset_path = str(Path(dataset_path))
    flow = TradingStrategyCreationFlow(
        dataset_path=resolved_dataset_path,
        asset_symbol=asset_symbol,
    )
    flow.plot()


if __name__ == "__main__":
    kickoff()
