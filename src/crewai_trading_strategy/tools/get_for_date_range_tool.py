from datetime import date
from typing import List, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from utils.historical_daily_prices_helper import HistoricalDailyPricesHelper, PriceDataPoint


class DateRangeQueryInput(BaseModel):
    """Input schema for querying historical price data by date range.

    The maximum date range is 30 days to limit output size.
    """

    start_date: str = Field(
        ...,
        description="Start date in ISO format (YYYY-MM-DD), e.g. '2020-09-18'.",
    )
    end_date: str = Field(
        ...,
        description="End date in ISO format (YYYY-MM-DD), e.g. '2020-09-20'.",
    )


class GetForDateRangeTool(BaseTool):
    """
    Tool for retrieving historical daily price data for a specific date range.
    Returns OHLCV (Date, Open, High, Low, Close, Volume) data points.
    Use this tool for small date ranges (max 30 days) to analyze price movements.
    """

    name: str = "Get Price Data For Date Range"
    description: str = "Retrieve historical price data for a date range."
    args_schema: Type[BaseModel] = DateRangeQueryInput

    helper: HistoricalDailyPricesHelper

    def model_post_init(self, __context) -> None:
        self.description = (
            "Retrieves historical daily OHLCV price data for a given date range. "
            "Use this tool when you need to analyze prices between two specific dates. "
            "The tool returns a list of price datapoints with Date, Open, High, Low, Close, and Volume. "
            f"Dates must be within the loaded dataset range: {self.helper.dataset_start_date} to "
            f"{self.helper.dataset_end_date}. "
            "The maximum date range is 30 days to limit output size, so it is only suitable for small analyses."
        )

    def gap_in_days(self, start_date: str, end_date: str) -> int:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        return (end - start).days

    def _run(self, start_date: str, end_date: str) -> str:
        if self.gap_in_days(start_date, end_date) > 30:
            return "Error: Date range exceeds maximum allowed span of 30 days."

        try:
            datapoints: List[PriceDataPoint] = self.helper.get_for_date_range(start_date, end_date)
            result_lines = [
                (
                    f"Found {len(datapoints)} price datapoints from {start_date} to {end_date} "
                    f"within dataset bounds {self.helper.dataset_start_date} to "
                    f"{self.helper.dataset_end_date}:\n"
                )
            ]

            for dp in datapoints:
                result_lines.append(
                    f"Date: {dp.date}, Open: ${dp.open:.2f}, High: ${dp.high:.2f}, "
                    f"Low: ${dp.low:.2f}, Close: ${dp.close:.2f}, Volume: {dp.volume:,}"
                )

            return "\n".join(result_lines)

        except ValueError as e:
            return f"Error retrieving {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
