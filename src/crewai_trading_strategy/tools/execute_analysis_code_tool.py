from datetime import date, datetime
import json
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class ExecuteCodeInput(BaseModel):
    code: str = Field(
        ...,
        description=(
            "Python code string that defines a function named 'run_on_data(df)' which takes "
            "a pandas DataFrame as input."
            " The code can only use safe libraries like "
            "numpy (aliased as np), pandas (aliased as pd), math, statistics, datetime, and re."
            "The libraries are pre-imported, so do not include import statements."
            "The dataframe contains the columns: Date, Open, High, Low, Close, Volume"
            "Do not double-escape line breaks (use actual line breaks in the string)."
        ),
    )


class ExecuteCodeTool(BaseTool):
    name: str = "Execute Custom Analysis Code on Data"
    description: str = (
        "Executes custom Python code to analyze the loaded historical price dataset. "
        "The code must define a function named 'run_on_data(df)'. "
        "Returns the result of that function (serialized)."
    )
    args_schema: Type[BaseModel] = ExecuteCodeInput

    helper: Any = Field(..., description="HistoricalDailyPricesHelper instance with loaded price data")

    def _to_jsonable(self, obj: Any) -> Any:
        if isinstance(obj, BaseModel):
            return obj.model_dump()

        if obj is None or isinstance(obj, (bool, int, float, str)):
            return obj

        if isinstance(obj, (date, datetime)):
            return obj.isoformat()

        if isinstance(obj, (bytes, bytearray)):
            return obj.decode("utf-8", errors="replace")

        if isinstance(obj, dict):
            return {str(k): self._to_jsonable(v) for k, v in obj.items()}

        if isinstance(obj, (list, tuple, set)):
            return [self._to_jsonable(v) for v in obj]

        try:
            import pandas as pd

            if isinstance(obj, pd.DataFrame):
                return obj.to_dict(orient="records")
            if isinstance(obj, pd.Series):
                return obj.to_dict()
        except Exception:
            pass

        try:
            import numpy as np

            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, (np.integer, np.floating, np.bool_)):
                return obj.item()
        except Exception:
            pass

        return str(obj)

    def _run(self, code: str) -> str:
        try:
            result: Any = self.helper.executeCode(code)
            payload = self._to_jsonable(result)
            return json.dumps(payload, ensure_ascii=False, indent=2)
        except ValueError as e:
            return f"Code validation error: {str(e)}"
        except Exception as e:
            return f"Execution error: {str(e)}"
