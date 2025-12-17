import textwrap

import pandas as pd
import pytest
from utils.historical_daily_prices_helper import HistoricalDailyPricesHelper
from utils.safe_python_code_executor import SafePythonCodeExecutor


@pytest.fixture()
def btc_csv_path(tmp_path):
    p = tmp_path / "btc.csv"
    p.write_text(textwrap.dedent("""\
        Date,Open,High,Low,Close,Volume
        2014-09-18,456.859985,456.859985,413.104004,424.440002,34483200
        2014-09-19,424.102997,427.834991,384.532013,394.795990,37919700
        2014-09-20,394.673004,423.295990,389.882996,408.903992,36863600
    """))
    return str(p)


def test_init_missing_columns_raises(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text(textwrap.dedent("""\
        Date,Open,Close
        2014-09-18,1,2
    """))
    with pytest.raises(ValueError, match="missing required columns"):
        HistoricalDailyPricesHelper(str(p))


def test_getForDateRange_valid(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)
    rows = ds.get_for_date_range("2014-09-19", "2014-09-20")

    assert len(rows) == 2
    assert rows[0].date.isoformat() == "2014-09-19"
    assert rows[1].date.isoformat() == "2014-09-20"
    assert float(rows[0].close) == pytest.approx(394.795990)

    # Optional: ensure alias-based serialization can produce "Date"
    dumped = rows[0].model_dump(by_alias=True)
    assert "Date" in dumped
    assert dumped["Date"].isoformat() == "2014-09-19"


def test_getForDateRange_out_of_bounds_raises(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)
    with pytest.raises(ValueError, match="outside the dataset bounds"):
        ds.get_for_date_range("2014-09-17", "2014-09-18")


def test_getForDateRange_start_after_end_raises(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)
    with pytest.raises(ValueError, match="start .* after end"):
        ds.get_for_date_range("2014-09-20", "2014-09-18")


def test_executeCode_success_returns_result(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)
    code = """
def run_on_data(df):
    return float(df["Close"].mean())
"""
    out = ds.executeCode(code)
    assert out == pytest.approx((424.440002 + 394.795990 + 408.903992) / 3.0)


def test_executeCode_provides_date_column(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)
    code = """
def run_on_data(df):
    # Helper now passes a df with a "Date" column (not just a DatetimeIndex).
    assert "Date" in df.columns
    # Return first date as ISO string to make the assertion easy/stable.
    return df["Date"].iloc[0].isoformat()
"""
    out = ds.executeCode(code)
    assert out == "2014-09-18"


def test_executeCode_requires_run_on_data(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)
    code = """
def not_runner(df):
    return 1
"""
    with pytest.raises(ValueError, match="run_on_data"):
        ds.executeCode(code)


def test_executeCode_signature_must_be_one_arg(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)
    code = """
def run_on_data(df, x):
    return 1
"""
    with pytest.raises(ValueError, match="exactly 1 argument"):
        ds.executeCode(code)


def test_executeCode_blocks_unsafe_import(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path, executor=SafePythonCodeExecutor())
    code = """
import os
def run_on_data(df):
    return 1
"""
    with pytest.raises(ValueError, match="Unsafe import"):
        ds.executeCode(code)


def test_executeCode_uses_copy_not_mutate_internal_df(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)
    original_first_close = float(ds.df.iloc[0]["Close"])

    code = """
def run_on_data(df):
    df.iloc[0, df.columns.get_loc("Close")] = 999999.0
    return float(df.iloc[0]["Close"])
"""
    out = ds.executeCode(code)
    assert out == 999999.0
    assert float(ds.df.iloc[0]["Close"]) == pytest.approx(original_first_close)


def test_get_df_until_date_exact_inclusive(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)

    out = ds.get_df_until_date("2014-09-19")

    assert len(out) == 2
    assert "Date" in out.columns
    assert pd.Timestamp(out["Date"].iloc[0]).date().isoformat() == "2014-09-18"
    assert pd.Timestamp(out["Date"].iloc[1]).date().isoformat() == "2014-09-19"


def test_get_df_until_date_timestamp_midday_includes_same_day(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)

    out = ds.get_df_until_date("2014-09-19 12:00:00")

    assert len(out) == 2
    assert pd.Timestamp(out["Date"].iloc[-1]).date().isoformat() == "2014-09-19"


def test_get_df_until_date_before_first_returns_empty(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)

    out = ds.get_df_until_date("2014-09-17")

    assert out.empty
    assert len(out) == 0
    # When empty, it should still be a DataFrame and still have the Date column
    assert "Date" in out.columns


def test_get_df_until_date_after_last_returns_all(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)

    out = ds.get_df_until_date("2014-09-21")

    assert len(out) == len(ds.df)
    assert "Date" in out.columns


def test_get_df_until_date_returns_copy_not_mutate_internal_df(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)
    original_first_close = float(ds.df.iloc[0]["Close"])

    out = ds.get_df_until_date("2014-09-19")
    out.iloc[0, out.columns.get_loc("Close")] = 999999.0

    assert float(ds.df.iloc[0]["Close"]) == pytest.approx(original_first_close)


def test_get_df_until_date_invalid_date_raises(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)

    with pytest.raises(Exception):
        ds.get_df_until_date("not-a-date")
