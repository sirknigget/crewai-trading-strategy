from typing import List

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent

from crewai.project import CrewBase, agent, crew, task, before_kickoff

from crewai_trading_strategy.constants import BTC_DATASET_PATH
from crewai_trading_strategy.guardrails.backtester_guardrail import ValidateBacktesterGuardrail
from crewai_trading_strategy.strategy_code_guidelines import get_strategy_code_guidelines
from crewai_trading_strategy.types import ImplementationTaskOutput
from utils.historical_daily_prices_helper import HistoricalDailyPricesHelper
from utils.strategy_backtester import StrategyBacktester

historicalPriceHelper = HistoricalDailyPricesHelper(csv_path=BTC_DATASET_PATH)
backtester = StrategyBacktester(prices=historicalPriceHelper)
backtest_code_guardrail = ValidateBacktesterGuardrail(backtester=backtester)

@CrewBase
class DummyDeveloperCrew():
    """DummyDeveloperCrew crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    @agent
    def dummy_developer(self) -> Agent:
        return Agent(
            config=self.agents_config['dummy_developer'],
            verbose=True,
        )

    @task
    def implement_strategy_task(self) -> Task:
        return Task(
            config=self.tasks_config['implement_strategy_task'],
            guardrails=[backtest_code_guardrail.get_guardrail_function()],
            guardrail_max_retries=5,
            output_pydantic=ImplementationTaskOutput,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,  # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
        )

