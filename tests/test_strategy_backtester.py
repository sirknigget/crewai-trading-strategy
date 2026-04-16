from datetime import timedelta

import pandas as pd
import pytest

from crewai_trading_strategy.constants import DEFAULT_DATASET_PATH
from utils.date_utils import parse_yyyy_mm_dd
from utils.historical_daily_prices_helper import HistoricalDailyPricesHelper
from utils.strategy_backtester import StrategyBacktester


@pytest.fixture()
def asset_csv_path(tmp_path):
    """
    5 daily candles with continuous pricing across consecutive dataset rows.

    And logical OHLC constraints:
    Low <= min(Open, Close) and High >= max(Open, Close)
    """
    df = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
            ),
            "Open": [100, 100, 105, 110, 120],
            "High": [102, 112, 120, 121, 130],
            "Low": [98, 95, 100, 108, 115],
            "Close": [100, 105, 110, 120, 125],
            "Volume": [1, 1, 1, 1, 1],
        }
    ).set_index("Date")

    path = tmp_path / "asset.csv"
    df.to_csv(path, index=True)
    return str(path)


def make_helper_and_bt(csv_path: str, asset_symbol: str = "ASSET"):
    helper = HistoricalDailyPricesHelper(csv_path)
    bt = StrategyBacktester(helper, asset_symbol=asset_symbol)
    return helper, bt


def test_start_date_requires_warmup_prior_candle(asset_csv_path):
    _, bt = make_helper_and_bt(asset_csv_path)

    code = "def run(df, holdings):\n    return []\n"
    res = bt.test_strategy("2024-01-01", "2024-01-01", code)

    assert isinstance(res, str)
    assert "requires at least 1 prior candle" in res


def test_date_range_out_of_bounds(asset_csv_path):
    _, bt = make_helper_and_bt(asset_csv_path)

    code = "def run(df, holdings):\n    return []\n"
    res = bt.test_strategy("2023-12-01", "2024-01-03", code)

    assert isinstance(res, str)
    assert "Date range validation error" in res


def test_missing_run_function(asset_csv_path):
    _, bt = make_helper_and_bt(asset_csv_path)

    code = "def not_run(df, holdings):\n    return []\n"
    res = bt.test_strategy("2024-01-02", "2024-01-03", code)

    assert isinstance(res, str)
    assert "Strategy code validation error" in res
    assert "run(df, holdings)" in res


def test_strategy_execution_error_returns_stacktrace(asset_csv_path):
    _, bt = make_helper_and_bt(asset_csv_path)

    code = """\
def run(df, holdings):
    1/0
"""
    res = bt.test_strategy("2024-01-02", "2024-01-02", code)

    assert isinstance(res, str)
    assert "Strategy execution error" in res
    assert "ZeroDivisionError" in res


def test_order_overspend_error(asset_csv_path):
    _, bt = make_helper_and_bt(asset_csv_path)

    code = """\
def run(df, holdings):
    return [{"action": "BUY", "asset": "ASSET", "amount": 10000.0}]
"""
    res = bt.test_strategy("2024-01-02", "2024-01-02", code)

    assert isinstance(res, str)
    assert "Order error: Insufficient USD for BUY" in res


def test_sell_nonexistent_holding_id(asset_csv_path):
    _, bt = make_helper_and_bt(asset_csv_path)

    code = """\
def run(df, holdings):
    return [{"action": "SELL", "holding_id": "H999", "amount": 1.0}]
"""
    res = bt.test_strategy("2024-01-02", "2024-01-02", code)

    assert isinstance(res, str)
    assert "Order error: SELL refers to non-existing holding_id" in res


def test_stop_loss_triggers_same_day_after_buy(asset_csv_path):
    _, bt = make_helper_and_bt(asset_csv_path)

    code = """\
def run(df, holdings):
    last = str(df["Date"].iloc[-1])[:10]
    if last == "2024-01-01":
        return [{"action": "BUY", "asset": "ASSET", "amount": 1.0, "stop_loss": 98.0}]
    return []
"""
    res = bt.test_strategy("2024-01-02", "2024-01-02", code)

    assert not isinstance(res, str)
    assert res.total_portfolio_usd == pytest.approx(9998.0, abs=1e-6)
    assert res.revenue_percent == pytest.approx((-2.0 / 10000.0) * 100.0, abs=1e-6)


def test_multi_day_take_profit_and_stop_loss(asset_csv_path):
    _, bt = make_helper_and_bt(asset_csv_path)

    code = """\
def run(df, holdings):
    last = str(df["Date"].iloc[-1])[:10]
    if last == "2024-01-01":
        return [{"action": "BUY", "asset": "ASSET", "amount": 1.0, "take_profit": 120.0}]
    if last == "2024-01-03":
        return [{"action": "BUY", "asset": "ASSET", "amount": 1.0, "stop_loss": 108.0}]
    return []
"""
    res = bt.test_strategy("2024-01-02", "2024-01-05", code)

    assert not isinstance(res, str)
    assert res.total_portfolio_usd == pytest.approx(10018.0, abs=1e-6)
    assert res.revenue_percent == pytest.approx((18.0 / 10000.0) * 100.0, abs=1e-6)
    assert sorted([h.asset for h in res.holdings]) == ["USD"]


def test_success_buy_then_sell_last_day_open(asset_csv_path):
    _, bt = make_helper_and_bt(asset_csv_path)

    code = """\
def run(df, holdings):
    last = str(df["Date"].iloc[-1])[:10]
    if last == "2024-01-01":
        return [{"action": "BUY", "asset": "ASSET", "amount": 1.0}]
    if last == "2024-01-04":
        for h in holdings:
            if h["asset"] == "ASSET":
                return [{"action": "SELL", "holding_id": h["holding_id"], "amount": h["amount"]}]
    return []
"""
    res = bt.test_strategy("2024-01-02", "2024-01-05", code)

    assert not isinstance(res, str)
    assert res.total_portfolio_usd == pytest.approx(10020.0, abs=1e-6)
    assert res.revenue_percent == pytest.approx((20.0 / 10000.0) * 100.0, abs=1e-6)
    assert sorted([h.asset for h in res.holdings]) == ["USD"]


def test_helper_function_allowed(asset_csv_path):
    _, bt = make_helper_and_bt(asset_csv_path)

    code = """\
def get_order():
    return [{"action": "BUY", "amount": 1.0, "asset": "ASSET"}]

def run(df, holdings):
    return get_order()
"""
    res = bt.test_strategy("2024-01-02", "2024-01-05", code)
    assert not isinstance(res, str)


def test_can_buy_up_to_usd_using_last_close_price(asset_csv_path):
    _, bt = make_helper_and_bt(asset_csv_path)

    code = """\
def run(df, holdings):
    last = str(df["Date"].iloc[-1])[:10]
    if last != "2024-01-01":
        return []

    last_close = float(df["Close"].iloc[-1])
    usd = 0.0
    for h in holdings:
        if h["asset"] == "USD":
            usd = float(h["amount"])
    amount = usd / last_close
    return [{"action": "BUY", "asset": "ASSET", "amount": amount}]
"""
    res = bt.test_strategy("2024-01-02", "2024-01-02", code)

    assert not isinstance(res, str)


def test_cannot_buy_more_than_usd_using_last_close_price(asset_csv_path):
    _, bt = make_helper_and_bt(asset_csv_path)

    code = """\
def run(df, holdings):
    last = str(df["Date"].iloc[-1])[:10]
    if last != "2024-01-01":
        return []

    last_close = float(df["Close"].iloc[-1])
    usd = 0.0
    for h in holdings:
        if h["asset"] == "USD":
            usd = float(h["amount"])

    max_amount = usd / last_close
    return [{"action": "BUY", "asset": "ASSET", "amount": max_amount + 0.01}]
"""
    res = bt.test_strategy("2024-01-02", "2024-01-02", code)

    assert isinstance(res, str)
    assert "Order error: Insufficient USD for BUY" in res


def test_non_daily_calendar_with_market_gap_still_uses_previous_available_candle(tmp_path):
    df = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-04", "2024-01-05", "2024-01-08"]),
            "Open": [100, 101, 110],
            "High": [101, 111, 115],
            "Low": [99, 100, 109],
            "Close": [100, 110, 112],
            "Volume": [1, 1, 1],
        }
    ).set_index("Date")
    path = tmp_path / "market_days.csv"
    df.to_csv(path, index=True)

    _, bt = make_helper_and_bt(str(path))

    code = """\
def run(df, holdings):
    return [{"action": "BUY", "asset": "ASSET", "amount": 1.0}] if str(df["Date"].iloc[-1])[:10] == "2024-01-05" else []
"""
    res = bt.test_strategy("2024-01-08", "2024-01-08", code)

    assert not isinstance(res, str)
    assert sorted([h.asset for h in res.holdings]) == ["ASSET", "USD"]

