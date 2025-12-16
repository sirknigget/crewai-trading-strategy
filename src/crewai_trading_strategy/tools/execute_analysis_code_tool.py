from typing import Type, Any, List
from datetime import date
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from utils.historical_daily_prices_helper import HistoricalDailyPricesHelper


class ExecuteCodeInput(BaseModel):
    """Input schema for executing custom Python code on the BTC dataset."""
    code: str = Field(
        ...,
        description=(
            "Python code string that defines a function named 'run_on_data(df)' which takes "
            "a pandas DataFrame as input. The code can only import safe libraries like "
            "numpy, pandas, math, statistics, datetime, and re. Example: "
            "def run_on_data(df):\\n    return df['Close'].mean()"
        )
    )


class ExecuteCodeTool(BaseTool):
    """
    Tool for executing custom Python analysis code on the full cryptocurrency price dataset.
    Allows dynamic data analysis with safety restrictions.
    The dataset contains daily historical prices for the cryptocurrency from 2014 to 2024.
    """
    name: str = "Execute Custom Analysis Code on Data"
    description: str = (
        "Executes custom Python code to analyze the Bitcoin historical price dataset. "
        "The code must define a function named 'run_on_data(df)' that receives a pandas DataFrame. "
        "Only safe data analysis libraries are allowed (numpy, pandas, math, statistics, datetime, re). "
        "Use this tool to perform calculations, statistical analysis, or custom transformations on the cryptocurrency data. "
        "Returns the result of the run_on_data function execution, which can contain an object with all your analysis results."
    )
    args_schema: Type[BaseModel] = ExecuteCodeInput

    helper: HistoricalDailyPricesHelper = Field(
        ...,
        description="HistoricalDailyPricesHelper instance with loaded BTC data"
    )

    def _run(self, code: str) -> str:
        """
        Execute the provided code and return the result.

        Returns a string representation of the code execution result.
        """
        try:
            result: Any = self.helper.executeCode(code)

            # Format the result based on type
            if isinstance(result, (int, float)):
                return f"Analysis result: {result}"
            elif isinstance(result, str):
                return f"Analysis result: {result}"
            elif hasattr(result, '__iter__') and not isinstance(result, str):
                # Handle lists, arrays, etc.
                return f"Analysis result: {list(result)}"
            else:
                return f"Analysis result: {str(result)}"

        except ValueError as e:
            return f"Code validation error: {str(e)}"
        except Exception as e:
            return f"Execution error: {str(e)}"
