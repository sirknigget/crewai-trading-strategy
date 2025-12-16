from crewai import Agent, Crew, Process, Task

from crewai.project import CrewBase, agent, crew, task

from crewai_trading_strategy.strategy_code_guidelines import get_strategy_code_guidelines


@CrewBase
class DummyDeveloperCrew():
    """DummyDeveloperCrew crew"""


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
            """,
            expected_output="""
                A string containing the Python code implementing the trading strategy. ONLY return the python code without any headers, explanations, or markdown formatting.
            """,
            agent=agent
        )

        return Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )
