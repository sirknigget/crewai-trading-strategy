# tests/test_strategy_backtester.py
import pandas as pd
import pytest

from utils.historical_daily_prices_helper import HistoricalDailyPricesHelper
from utils.strategy_backtester import StrategyBacktester

@pytest.fixture()
def btc_csv_path(tmp_path):
    """
    5 daily candles with BTC-style continuity:
    Open[t] == Close[t-1]

    And logical OHLC constraints:
    Low <= min(Open, Close) and High >= max(Open, Close)
    """
    df = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
            ),
            "Open":  [100, 100, 105, 110, 120],
            "High":  [102, 112, 120, 121, 130],
            "Low":   [98,   95, 100, 108, 115],
            "Close": [100, 105, 110, 120, 125],
            "Volume": [1, 1, 1, 1, 1],
        }
    ).set_index("Date")

    path = tmp_path / "btc.csv"
    df.to_csv(path, index=True)
    return str(path)


def make_helper_and_bt(csv_path: str):
    helper = HistoricalDailyPricesHelper(csv_path)
    bt = StrategyBacktester(helper)
    return helper, bt


def test_start_date_requires_warmup_prior_candle(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    code = "def run(df, holdings):\n    return []\n"
    res = bt.test_strategy("2024-01-01", "2024-01-01", code)

    assert isinstance(res, str)
    assert "requires at least 1 prior candle" in res


def test_date_range_out_of_bounds(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    code = "def run(df, holdings):\n    return []\n"
    res = bt.test_strategy("2023-12-01", "2024-01-03", code)

    assert isinstance(res, str)
    assert "Date range validation error" in res


def test_missing_run_function(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    code = "def not_run(df, holdings):\n    return []\n"
    res = bt.test_strategy("2024-01-02", "2024-01-03", code)

    assert isinstance(res, str)
    assert "Strategy code validation error" in res
    assert "run(df, holdings)" in res


def test_strategy_execution_error_returns_stacktrace(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    code = """\
def run(df, holdings):
    1/0
"""
    res = bt.test_strategy("2024-01-02", "2024-01-02", code)

    assert isinstance(res, str)
    assert "Strategy execution error" in res
    assert "ZeroDivisionError" in res


def test_order_overspend_error(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    # Execution day 2024-01-02 Open=100, buying 10000 BTC costs 1,000,000 USD -> should fail.
    code = """\
def run(df, holdings):
    return [{"action": "BUY", "asset": "BTC", "amount": 10000.0}]
"""
    res = bt.test_strategy("2024-01-02", "2024-01-02", code)

    assert isinstance(res, str)
    assert "Order error: Insufficient USD for BUY" in res


def test_sell_nonexistent_holding_id(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    code = """\
def run(df, holdings):
    return [{"action": "SELL", "holding_id": "H999", "amount": 1.0}]
"""
    res = bt.test_strategy("2024-01-02", "2024-01-02", code)

    assert isinstance(res, str)
    assert "Order error: SELL refers to non-existing holding_id" in res


def test_stop_loss_triggers_same_day_after_buy(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    # For execution day 2024-01-02, df includes up to 2024-01-01.
    # Strategy buys based on last close (2024-01-01 Close=100).
    # Execution price on 2024-01-02 Open=100 (same as last close).
    # Day2 Low=95 triggers stop_loss=98 => sell at 98 => -2 USD on 1 BTC.
    code = """\
def run(df, holdings):
    last = str(df["Date"].iloc[-1])[:10]
    if last == "2024-01-01":
        return [{"action": "BUY", "asset": "BTC", "amount": 1.0, "stop_loss": 98.0}]
    return []
"""
    res = bt.test_strategy("2024-01-02", "2024-01-02", code)

    assert not isinstance(res, str)
    assert res.total_portfolio_usd == pytest.approx(9998.0, abs=1e-6)
    assert res.revenue_percent == pytest.approx((-2.0 / 10000.0) * 100.0, abs=1e-6)


def test_multi_day_take_profit_and_stop_loss(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    # Multi-day strategy (uses "current price == last close" for sizing/logic):
    #
    # - On 2024-01-02: buy 1 BTC with take_profit=120
    #   Bought at 2024-01-02 Open=100 (== 2024-01-01 Close=100).
    #   TP triggers 2024-01-03 High=120 => sell at 120 => +20
    #
    # - On 2024-01-04: buy 1 BTC with stop_loss=108
    #   Bought at 2024-01-04 Open=110 (== 2024-01-03 Close=110).
    #   SL triggers 2024-01-04 Low=108 => sell at 108 => -2
    #
    # Net: +18 => 10018
    code = """\
def run(df, holdings):
    last = str(df["Date"].iloc[-1])[:10]
    if last == "2024-01-01":
        return [{"action": "BUY", "asset": "BTC", "amount": 1.0, "take_profit": 120.0}]
    if last == "2024-01-03":
        return [{"action": "BUY", "asset": "BTC", "amount": 1.0, "stop_loss": 108.0}]
    return []
"""
    res = bt.test_strategy("2024-01-02", "2024-01-05", code)

    assert not isinstance(res, str)
    assert res.total_portfolio_usd == pytest.approx(10018.0, abs=1e-6)
    assert res.revenue_percent == pytest.approx((18.0 / 10000.0) * 100.0, abs=1e-6)

    # Both positions should be closed (TP then SL)
    assert sorted([h.asset for h in res.holdings]) == ["USD"]


def test_success_buy_then_sell_last_day_open(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    # Buy on 2024-01-02 using last close (2024-01-01 Close=100).
    # Sell on 2024-01-05 at Open=120 (== 2024-01-04 Close=120).
    # PnL: +20
    code = """\
def run(df, holdings):
    last = str(df["Date"].iloc[-1])[:10]
    if last == "2024-01-01":
        return [{"action": "BUY", "asset": "BTC", "amount": 1.0}]
    if last == "2024-01-04":
        for h in holdings:
            if h["asset"] == "BTC":
                return [{"action": "SELL", "holding_id": h["holding_id"], "amount": h["amount"]}]
    return []
"""
    res = bt.test_strategy("2024-01-02", "2024-01-05", code)

    assert not isinstance(res, str)
    assert res.total_portfolio_usd == pytest.approx(10020.0, abs=1e-6)
    assert res.revenue_percent == pytest.approx((20.0 / 10000.0) * 100.0, abs=1e-6)
    assert sorted([h.asset for h in res.holdings]) == ["USD"]


def test_helper_function_allowed(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    code = """\
def get_order():
    return [{"action": "BUY", "amount": 1.0, "asset": "BTC"}]

def run(df, holdings):
    return get_order()
"""
    res = bt.test_strategy("2024-01-02", "2024-01-05", code)
    assert not isinstance(res, str)


def test_can_buy_up_to_usd_using_last_close_price(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    # Strategy assumes "current BTC price == last day close".
    # On 2024-01-02, last close is 2024-01-01 Close=100, so with 10000 USD:
    # max buy amount is 10000 / 100 = 100 BTC (should succeed).
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
    amount = usd / last_close  # exact max
    return [{"action": "BUY", "asset": "BTC", "amount": amount}]
"""
    res = bt.test_strategy("2024-01-02", "2024-01-02", code)

    assert not isinstance(res, str)
    # We only assert it runs (no error); valuation rules at end-of-day can vary by engine.


def test_cannot_buy_more_than_usd_using_last_close_price(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    # Same assumption as above, but requests slightly more than max.
    # On 2024-01-02 last close is 100; 100.01 BTC costs 10001 USD > 10000 -> fail.
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
    return [{"action": "BUY", "asset": "BTC", "amount": max_amount + 0.01}]
"""
    res = bt.test_strategy("2024-01-02", "2024-01-02", code)

    assert isinstance(res, str)
    assert "Order error: Insufficient USD for BUY" in res
