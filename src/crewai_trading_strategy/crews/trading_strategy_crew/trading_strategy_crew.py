from crewai import Agent, Crew, Process, Task
from crewai.memory import ShortTermMemory
from crewai.memory.storage.rag_storage import RAGStorage
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List

from pydantic import Field, BaseModel

from crewai_trading_strategy.constants import BTC_DATASET_PATH
from crewai_trading_strategy.guardrails.backtester_guardrail import ValidateBacktesterGuardrail
from crewai_trading_strategy.tools.execute_analysis_code_tool import ExecuteCodeTool
from crewai_trading_strategy.tools.get_for_date_range_tool import GetForDateRangeTool
from crewai_trading_strategy.tools.run_strategy_backtest_tool import RunStrategyBacktestTool
from crewai_trading_strategy.types import ImplementationTaskOutput
from utils.historical_daily_prices_helper import HistoricalDailyPricesHelper
from utils.strategy_backtester import StrategyBacktester

# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

# Initialize the helper with your CSV
historicalPriceHelper = HistoricalDailyPricesHelper(csv_path=BTC_DATASET_PATH)
backtester = StrategyBacktester(prices=historicalPriceHelper)

# Create tool instances
date_range_tool = GetForDateRangeTool(helper=historicalPriceHelper)
execute_code_tool = ExecuteCodeTool(helper=historicalPriceHelper)
backtest_code_guardrail = ValidateBacktesterGuardrail(backtester=backtester)

@CrewBase
class TradingStrategyCrew():
    """TradingStrategyCrew crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    @agent
    def strategy_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['strategy_researcher'],
            verbose=True,
            tools=[date_range_tool, execute_code_tool],
            max_iter=30,
        )

    @agent
    def engineering_lead(self) -> Agent:
        return Agent(
            config=self.agents_config['engineering_lead'],
            verbose=True,
            tools=[],
        )

    @agent
    def developer(self) -> Agent:
        return Agent(
            config=self.agents_config['developer'],
            verbose=True,
            allow_code_execution=True,
            code_execution_mode="safe",
        )

    @task
    def research_strategy_task(self) -> Task:
        return Task(
            config=self.tasks_config['research_strategy_task'],
        )

    @task
    def design_strategy_task(self) -> Task:
        return Task(
            config=self.tasks_config['design_strategy_task'],
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
        """Creates the TradingStrategyCrew crew"""
        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
        )
