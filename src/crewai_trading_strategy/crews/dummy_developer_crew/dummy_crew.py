from typing import List

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task

from crewai_trading_strategy.guardrails.backtester_guardrail import ValidateBacktesterGuardrail
from crewai_trading_strategy.types import ImplementationTaskOutput
from utils.historical_daily_prices_helper import HistoricalDailyPricesHelper
from utils.strategy_backtester import StrategyBacktester


@CrewBase
class DummyDeveloperCrew:
    """DummyDeveloperCrew crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    def __init__(
        self,
        historical_price_helper: HistoricalDailyPricesHelper,
        backtester: StrategyBacktester,
    ):
        self._historical_price_helper = historical_price_helper
        self._backtester = backtester
        self._backtest_code_guardrail = ValidateBacktesterGuardrail(backtester=backtester)

    @agent
    def dummy_developer(self) -> Agent:
        return Agent(
            config=self.agents_config["dummy_developer"],
            verbose=True,
        )

    @task
    def implement_strategy_task(self) -> Task:
        return Task(
            config=self.tasks_config["implement_strategy_task"],
            guardrails=[self._backtest_code_guardrail.get_guardrail_function()],
            guardrail_max_retries=5,
            output_pydantic=ImplementationTaskOutput,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
