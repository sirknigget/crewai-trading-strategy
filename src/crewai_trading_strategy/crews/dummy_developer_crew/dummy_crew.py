from crewai import Agent, Crew, Process, Task

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

    previous_attempts_info = ""

    @before_kickoff
    def prepare_inputs(self, inputs):
        self.previous_attempts_info = inputs.get("previous_attempts_info", "")

    @crew
    def crew(self) -> Crew:
        agent = Agent(
            name="dummy_developer",
            role="Developer that provides dummy implementation",
            goal="Provide a dummy implementation for testing purposes",
            backstory="You are an experienced developer with attention to detail",
            verbose=True,
            allow_code_execution=True,
            code_execution_mode="safe",
        )

        task = Task(
            name="implement_strategy_task",
            description=f"""
                Create a dummy implementation of a trading strategy according to the following API guidelines:
                {get_strategy_code_guidelines()}
                
                {self.previous_attempts_info}
            """,
            expected_output="""
                The Python code implementing the trading strategy. ONLY return the python code without any headers, explanations, or markdown formatting.
            """,
            agent=agent,
            guardrails=[backtest_code_guardrail.get_guardrail_function()],
            guardrail_max_retries=5,
            output_pydantic=ImplementationTaskOutput,
        )

        return Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )
