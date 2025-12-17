from pydantic import BaseModel, Field


class ImplementationTaskOutput(BaseModel):
    """ Implementation contains the trading strategy code """
    implementation: str = Field(description="Runnable Python code for the trading strategy, conforming with guidelines")