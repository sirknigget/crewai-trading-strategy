# tests/test_btc_prices.py
import textwrap
import pytest
from utils.historical_daily_prices_helper import HistoricalDailyPricesHelper
from utils.safe_python_code_executor import SafePythonCodeExecutor


@pytest.fixture()
def btc_csv_path(tmp_path):
    p = tmp_path / "btc.csv"
    p.write_text(textwrap.dedent("""\
        Date,Open,High,Low,Close,Adj Close,Volume
        2014-09-18,456.859985,456.859985,413.104004,424.440002,424.440002,34483200
        2014-09-19,424.102997,427.834991,384.532013,394.795990,394.795990,37919700
        2014-09-20,394.673004,423.295990,389.882996,408.903992,408.903992,36863600
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
    rows = ds.getForDateRange("2014-09-19", "2014-09-20")
    assert len(rows) == 2
    assert rows[0].date.isoformat() == "2014-09-19"
    assert rows[1].date.isoformat() == "2014-09-20"
    assert float(rows[0].close) == pytest.approx(394.795990)


def test_getForDateRange_out_of_bounds_raises(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)
    with pytest.raises(ValueError, match="outside the dataset bounds"):
        ds.getForDateRange("2014-09-17", "2014-09-18")


def test_getForDateRange_start_after_end_raises(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)
    with pytest.raises(ValueError, match="start .* after end"):
        ds.getForDateRange("2014-09-20", "2014-09-18")


def test_executeCode_success_returns_result(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)
    code = """
def runOnData(df):
    return float(df["Close"].mean())
"""
    out = ds.executeCode(code)
    assert out == pytest.approx((424.440002 + 394.795990 + 408.903992) / 3.0)


def test_executeCode_requires_runOnData(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)
    code = """
def not_runner(df):
    return 1
"""
    with pytest.raises(ValueError, match="runOnData"):
        ds.executeCode(code)


def test_executeCode_signature_must_be_one_arg(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)
    code = """
def runOnData(df, x):
    return 1
"""
    with pytest.raises(ValueError, match="exactly 1 argument"):
        ds.executeCode(code)


def test_executeCode_blocks_unsafe_import(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path, executor=SafePythonCodeExecutor())
    code = """
import os
def runOnData(df):
    return 1
"""
    with pytest.raises(ValueError, match="Unsafe import"):
        ds.executeCode(code)


def test_executeCode_uses_copy_not_mutate_internal_df(btc_csv_path):
    ds = HistoricalDailyPricesHelper(btc_csv_path)
    original_first_close = float(ds.df.iloc[0]["Close"])

    code = """
def runOnData(df):
    df.iloc[0, df.columns.get_loc("Close")] = 999999.0
    return float(df.iloc[0]["Close"])
"""
    out = ds.executeCode(code)
    assert out == 999999.0
    assert float(ds.df.iloc[0]["Close"]) == pytest.approx(original_first_close)
