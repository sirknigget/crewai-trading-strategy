from typing import Type, Any
from datetime import date, datetime
import json

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class ExecuteCodeInput(BaseModel):
    code: str = Field(..., description=(
        "Python code string that defines a function named 'run_on_data(df)' which takes "
        "a pandas DataFrame as input. The code can only import safe libraries like "
        "numpy, pandas, math, statistics, datetime, and re."
        "The dataframe contains the columns: Date, Open, High, Low, Close, Volume"
    ))


class ExecuteCodeTool(BaseTool):
    name: str = "Execute Custom Analysis Code on Data"
    description: str = (
        "Executes custom Python code to analyze the Bitcoin historical price dataset. "
        "The code must define a function named 'run_on_data(df)'. "
        "Returns the result of that function (serialized)."
    )
    args_schema: Type[BaseModel] = ExecuteCodeInput

    helper: Any = Field(..., description="HistoricalDailyPricesHelper instance with loaded BTC data")

    def _to_jsonable(self, obj: Any) -> Any:
        # Pydantic v2
        if isinstance(obj, BaseModel):
            return obj.model_dump()

        # Common primitives
        if obj is None or isinstance(obj, (bool, int, float, str)):
            return obj

        # Dates
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()

        # Bytes
        if isinstance(obj, (bytes, bytearray)):
            return obj.decode("utf-8", errors="replace")

        # Dict-like
        if isinstance(obj, dict):
            return {str(k): self._to_jsonable(v) for k, v in obj.items()}

        # List-like
        if isinstance(obj, (list, tuple, set)):
            return [self._to_jsonable(v) for v in obj]

        # Optional: pandas / numpy support (only if those libs are available in your env)
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

        # Fallback: stringify unknown objects
        return str(obj)

    def _run(self, code: str) -> str:
        try:
            result: Any = self.helper.executeCode(code)

            payload = self._to_jsonable(result)

            # Return a stable, parseable string (good for agents + downstream steps)
            return json.dumps(payload, ensure_ascii=False, indent=2)

        except ValueError as e:
            return f"Code validation error: {str(e)}"
        except Exception as e:
            return f"Execution error: {str(e)}"
