#!/usr/bin/env python
import json
from random import randint

from crewai_trading_strategy.crews.trading_strategy_crew.strategy_code_guidelines import get_stratregy_code_guidelines
from crewai_trading_strategy.crews.trading_strategy_crew.trading_strategy_crew import TradingStrategyCrew
from pydantic import BaseModel
from crewai.flow import Flow, listen, start

class TradingStrategyCreationState(BaseModel):
    strategy_code: str = ""

inputs: dict = {
    "coin_symbol": "BTC",
    "dataset_start_date": "2017-11-10",
    "dataset_end_date": "2024-01-19",
    "strategy_code_guidelines": get_stratregy_code_guidelines()
}

class TradingStrategyCreationFlow(Flow[TradingStrategyCreationState]):

    @start()
    def start(self) -> TradingStrategyCreationState:

        crew_output = TradingStrategyCrew().crew().kickoff(inputs=inputs)

        print("Crew output:\n" + json.dumps(crew_output, indent=2))

        implementation_task = next(t for t in crew_output.tasks_output if t.name == "implement_strategy_task")
        self.state.strategy_code = implementation_task.raw
        return self.state


def kickoff():
    flow = TradingStrategyCreationFlow()
    flow.kickoff()


def plot():
    flow = TradingStrategyCreationFlow()
    flow.plot()

if __name__ == "__main__":
    kickoff()
