import inspect
from typing import Optional, Union, Any
from pydantic import BaseModel, Field
import datetime as dt
import pandas as pd
from utils.safe_python_code_executor import SafePythonCodeExecutor
from datetime import date

DateLike = Union[str, dt.date, dt.datetime, pd.Timestamp]

class PriceDataPoint(BaseModel):
    date: dt.date
    open: float = Field(alias="Open")
    high: float = Field(alias="High")
    low: float = Field(alias="Low")
    close: float = Field(alias="Close")
    volume: int = Field(alias="Volume")

class HistoricalDailyPricesHelper:
    REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

    def __init__(self, csv_path: str, executor: Optional[SafePythonCodeExecutor] = None):
        df = pd.read_csv(csv_path, parse_dates=True, index_col="Date")
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("CSV 'Date' column could not be parsed into a DatetimeIndex.")

        missing = [c for c in self.REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"CSV is missing required columns: {missing}")

        self.df = df.sort_index()
        self._executor = executor or SafePythonCodeExecutor()

    def _to_timestamp(self, value: DateLike, label: str) -> pd.Timestamp:
        try:
            ts = pd.to_datetime(value, utc=False)
        except Exception as e:
            raise ValueError(f"Invalid {label} date: {value!r}. Could not parse.") from e
        return pd.Timestamp(ts).normalize()

    def get_df_until_date(self, date: str) -> pd.DataFrame:
        cutoff = pd.to_datetime(date)
        end = self.df.index.searchsorted(cutoff, side="right")
        return self.df.iloc[:end].copy()

    def get_for_date_range(self, start: DateLike, end: DateLike) -> list[PriceDataPoint]:
        start_ts = self._to_timestamp(start, "start")
        end_ts = self._to_timestamp(end, "end")

        if start_ts > end_ts:
            raise ValueError(f"Invalid range: start ({start_ts.date()}) is after end ({end_ts.date()}).")

        min_ts = pd.Timestamp(self.df.index.min()).normalize()
        max_ts = pd.Timestamp(self.df.index.max()).normalize()

        if start_ts < min_ts or end_ts > max_ts:
            raise ValueError(
                "Date range is outside the dataset bounds: "
                f"requested [{start_ts.date()} .. {end_ts.date()}], "
                f"available [{min_ts.date()} .. {max_ts.date()}]."
            )

        subset = self.df.loc[start_ts:end_ts]
        if subset.empty:
            raise ValueError(
                f"No rows found in range [{start_ts.date()} .. {end_ts.date()}]. "
                "The dataset may not contain those specific dates."
            )

        out: list[PriceDataPoint] = []
        for idx, row in subset.iterrows():
            payload = row.to_dict()
            payload["date"] = pd.Timestamp(idx).date()
            out.append(PriceDataPoint.model_validate(payload))
        return out

    def executeCode(self, code: str) -> Any:
        compiled = self._executor.check_and_compile(code)
        ns = self._executor.execute_compiled(compiled)

        runner = ns.get("run_on_data")
        if not callable(runner):
            raise ValueError("code must define a top-level function named run_on_data(df).")

        # Signature check stays in this class. [web:28]
        sig = inspect.signature(runner)
        params = list(sig.parameters.values())

        if len(params) != 1:
            raise ValueError(f"run_on_data must accept exactly 1 argument (df), found {len(params)}.")

        if params[0].kind not in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            raise ValueError("run_on_data(df) must take df as a positional argument.")

        return runner(self.df.copy())
