#!/usr/bin/env python
import json
from datetime import date, timedelta, datetime
from random import randint

from crewai_trading_strategy.constants import BTC_DATASET_START_DATE, BTC_DATASET_END_DATE
from crewai_trading_strategy.crews.dummy_developer_crew.dummy_crew import DummyDeveloperCrew
from crewai_trading_strategy.crews.trading_strategy_crew.trading_strategy_crew import TradingStrategyCrew
from pydantic import BaseModel
from crewai.flow import Flow, listen, start

from crewai_trading_strategy.strategy_code_guidelines import get_strategy_code_guidelines
from utils.code_utils import strip_llm_formatting
from utils.date_utils import parse_yyyy_mm_dd
from utils.historical_daily_prices_helper import HistoricalDailyPricesHelper
from utils.json_utils import dump_object
from utils.strategy_backtester import StrategyBacktester


class TradingStrategyCreationState(BaseModel):
    strategy_code: str = ""

inputs: dict = {
    "coin_symbol": "BTC",
    "dataset_start_date": BTC_DATASET_START_DATE,
    "dataset_end_date": BTC_DATASET_END_DATE,
    "strategy_code_guidelines": get_strategy_code_guidelines()
}

class TradingStrategyCreationFlow(Flow[TradingStrategyCreationState]):

    @start()
    def start(self) -> TradingStrategyCreationState:

        crew_output = TradingStrategyCrew().crew().kickoff(inputs=inputs)
        implementation_task = next(t for t in crew_output.tasks_output if t.name == "implement_strategy_task")
        strategy_code = implementation_task.pydantic.implementation
        strategy_code = strip_llm_formatting(strategy_code)

        # save code to output file
        with open(f"output/trading_strategy_implementation.py", "w") as f:
            f.write(strategy_code)

        self.state.strategy_code = strategy_code
        return self.state

    @listen(start)
    def backtest_strategy(self) -> TradingStrategyCreationState:
        print("\n\n=== STRATEGY CODE ===\n\n")
        print(self.state.strategy_code)

        historicalPriceHelper = HistoricalDailyPricesHelper(csv_path="data/BTC-USD_2014_2024.csv")
        backtester = StrategyBacktester(prices=historicalPriceHelper)
        start_date = parse_yyyy_mm_dd(BTC_DATASET_START_DATE) + timedelta(days=1)
        end_date = parse_yyyy_mm_dd(BTC_DATASET_END_DATE)
        result = backtester.test_strategy(start_date, end_date, self.state.strategy_code)

        print("\n\n=== BACKTEST RESULT ===\n\n")
        print(dump_object(result))

        return self.state


def kickoff():
    flow = TradingStrategyCreationFlow()
    flow.kickoff()


def plot():
    flow = TradingStrategyCreationFlow()
    flow.plot()

if __name__ == "__main__":
    kickoff()
