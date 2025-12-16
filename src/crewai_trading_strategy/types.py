from pydantic import BaseModel, Field


class ImplementationTaskOutput(BaseModel):
    """ Implementation contains the trading strategy code, and unit test code """
    implementation: str = Field(description="Runnable Python code for the trading strategy, conforming with guidelines")
    unit_tests: str = Field(description="A test suite for the trading strategy code providing coverage of happy and edge cases")
