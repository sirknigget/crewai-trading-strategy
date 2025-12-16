from typing import Type, Any, List
from datetime import date
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from utils.historical_daily_prices_helper import HistoricalDailyPricesHelper, PriceDataPoint


class DateRangeQueryInput(BaseModel):
    """Input schema for querying BTC price data by date range."""
    start_date: str = Field(
        ...,
        description="Start date in ISO format (YYYY-MM-DD), e.g., '2014-09-18'"
    )
    end_date: str = Field(
        ...,
        description="End date in ISO format (YYYY-MM-DD), e.g., '2014-09-20'"
    )


class GetForDateRangeTool(BaseTool):
    """
    Tool for retrieving Bitcoin historical daily price data for a specific date range.
    Returns OHLCV (Open, High, Low, Close, Volume) data points.
    The maximum date range is 30 days to limit output size.
    """
    name: str = "Get BTC Price Data For Date Range"
    description: str = (
        "Retrieves Bitcoin historical daily OHLCV price data for a given date range. "
        "Use this tool when you need to analyze BTC prices between two specific dates. "
        "The tool returns a list of price datapoints with Open, High, Low, Close, and Volume. "
        "Dates must be within the available dataset range (2014-09-18 onwards)."
    )
    args_schema: Type[BaseModel] = DateRangeQueryInput

    # Instance of the helper class (passed during initialization)
    helper: HistoricalDailyPricesHelper

    def gap_in_days(self, start_date: str, end_date: str) -> int:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        return (end - start).days

    def _run(self, start_date: str, end_date: str) -> str:
        """
        Execute the date range query and return formatted results.

        Returns a formatted string representation of the price data
        that's suitable for LLM consumption.
        """

        # Enforce maximum date range of 30 days
        if self.gap_in_days(start_date, end_date) > 30:
            return "Error: Date range exceeds maximum allowed span of 30 days."

        try:
            datapoints: List[PriceDataPoint] = self.helper.get_for_date_range(
                start_date,
                end_date
            )

            # Format results for LLM readability
            result_lines = [
                f"Found {len(datapoints)} price datapoints from {start_date} to {end_date}:\n"
            ]

            for dp in datapoints:
                result_lines.append(
                    f"Date: {dp.date}, Open: ${dp.open:.2f}, High: ${dp.high:.2f}, "
                    f"Low: ${dp.low:.2f}, Close: ${dp.close:.2f}, Volume: {dp.volume:,}"
                )

            return "\n".join(result_lines)

        except ValueError as e:
            return f"Error retrieving  {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"


