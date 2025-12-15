#!/usr/bin/env python
from random import randint

from crewai_trading_strategy.crews.trading_strategy_crew.trading_strategy_crew import TradingStrategyCrew
from pydantic import BaseModel
from crewai.flow import Flow, listen, start

class TradingStrategyCreationState(BaseModel):
    pass

inputs: dict = {
    "coin_symbol": "BTC",
    "dataset_start_date": "2017-11-10",
    "dataset_end_date": "2024-01-19",
}

class TradingStrategyCreationFlow(Flow[TradingStrategyCreationState]):

    @start()
    def start_research(self) -> TradingStrategyCreationState:

        TradingStrategyCrew().crew().kickoff(inputs=inputs)
        return TradingStrategyCreationState()


def kickoff():
    flow = TradingStrategyCreationFlow()
    flow.kickoff()


def plot():
    flow = TradingStrategyCreationFlow()
    flow.plot()

if __name__ == "__main__":
    kickoff()
