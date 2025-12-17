#!/usr/bin/env python
import json
from datetime import date, timedelta, datetime
from random import randint

from crewai_trading_strategy.constants import BTC_DATASET_START_DATE, BTC_DATASET_END_DATE
from crewai_trading_strategy.crews.dummy_developer_crew.dummy_crew import DummyDeveloperCrew
from crewai_trading_strategy.crews.trading_strategy_crew.trading_strategy_crew import TradingStrategyCrew
from pydantic import BaseModel
from crewai.flow import Flow, listen, start, router, or_

from crewai_trading_strategy.strategy_code_guidelines import get_strategy_code_guidelines
from utils.code_utils import strip_llm_formatting
from utils.date_utils import parse_yyyy_mm_dd
from utils.historical_daily_prices_helper import HistoricalDailyPricesHelper
from utils.json_utils import dump_object
from utils.strategy_backtester import StrategyBacktester, BacktestResult

MAX_ATTEMPTS = 3

class TradingStrategyAttempt(BaseModel):
    strategy_outline: str
    strategy_design: str
    strategy_implementation: str
    backtest_result: BacktestResult

class TradingStrategyCreationState(BaseModel):
    attempts_log: list[TradingStrategyAttempt] = []

BASE_INPUTS: dict = {
    "coin_symbol": "BTC",
    "dataset_start_date": BTC_DATASET_START_DATE,
    "dataset_end_date": BTC_DATASET_END_DATE,
    "strategy_code_guidelines": get_strategy_code_guidelines()
}

class TradingStrategyCreationFlow(Flow[TradingStrategyCreationState]):

    historicalPriceHelper = HistoricalDailyPricesHelper(csv_path="data/BTC-USD_2014_2024.csv")
    backtester = StrategyBacktester(prices=historicalPriceHelper)

    def create_previous_attempts_info(self) -> str:
        if len(self.state.attempts_log) == 0:
            return "This is the first attempt to create the trading strategy."
        else:
            info = "Examine the previous attempts to create the trading strategy and build upon them to improve:\n"
            info += f"Previous {len(self.state.attempts_log)} attempts to create the trading strategy:\n"
            for i, attempt in enumerate(self.state.attempts_log, start=1):
                info += f"\n--- Attempt {i} ---\n"
                info += f"Strategy Outline:\n{attempt.strategy_outline}\n"
                info += f"Strategy Implementation:\n{attempt.strategy_implementation}\n"
                # info += f"Strategy Design:\n{attempt.strategy_design}\n" # No need to let the researcher see the design
                info += f"Backtest Result:\n{dump_object(attempt.backtest_result)}\n"
            return info

    def backtest_strategy(self, implementation_code) -> BacktestResult:
        print("\n\n=== STRATEGY CODE TO BACKTEST ===\n\n")
        print(implementation_code)

        start_date = parse_yyyy_mm_dd(BTC_DATASET_START_DATE) + timedelta(days=1)
        end_date = parse_yyyy_mm_dd(BTC_DATASET_END_DATE)
        result = self.backtester.test_strategy(start_date, end_date, implementation_code)

        print("\n\n=== BACKTEST RESULT ===\n\n")
        print(dump_object(result))

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
        backtest_result = backtest_result

        attempt_log = TradingStrategyAttempt(
            strategy_outline=strategy_outline,
            strategy_design=strategy_design,
            strategy_implementation=strategy_implementation,
            backtest_result=backtest_result,
        )
        return attempt_log

    @start()
    def start(self) -> TradingStrategyCreationState:
        print("Starting Trading Strategy Creation Flow")

        self.state.attempts_log = []
        return self.state

    @router(or_("start", "continue"))
    def main_loop(self) -> str:
        print(f"\n\n=== ATTEMPT {len(self.state.attempts_log) + 1} TO CREATE TRADING STRATEGY ===\n\n")

        inputs = BASE_INPUTS.copy()
        inputs["previous_attempts_info"] = self.create_previous_attempts_info()

        crew_output = TradingStrategyCrew().crew().kickoff(inputs=inputs)

        attempt_log = self.handle_crew_output(crew_output)
        self.state.attempts_log.append(attempt_log)

        if len(self.state.attempts_log) >= MAX_ATTEMPTS:
            return "break"
        return "continue"

    @listen("break")
    def finish(self):
        print("\n\n=== TRADING STRATEGY CREATION FLOW FINISHED ===\n\n")

        best_attempt = max(self.state.attempts_log, key=lambda attempt: attempt.backtest_result.revenue_percent)
        print("Best Attempt Backtest Result:")
        print(dump_object(best_attempt.backtest_result))
        print("\nBest Attempt Strategy Implementation Code:")
        print(best_attempt.strategy_implementation)

        # Write the best strategy's files to output directory
        with open("output/trading_strategy_outline.md", "w") as f:
            f.write(best_attempt.strategy_outline)
        
        with open("output/trading_strategy_design.md", "w") as f:
            f.write(best_attempt.strategy_design)
        
        with open("output/trading_strategy_implementation.py", "w") as f:
            f.write(best_attempt.strategy_implementation)

        # Log full attempts to a file
        with open("output/trading_strategy_creation_attempts_log.json", "w") as f:
            f.write(dump_object(self.state.attempts_log))

def kickoff():
    flow = TradingStrategyCreationFlow()
    flow.kickoff()


def plot():
    flow = TradingStrategyCreationFlow()
    flow.plot()

if __name__ == "__main__":
    kickoff()
