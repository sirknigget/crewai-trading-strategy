# tests/test_strategy_backtester.py
import pandas as pd
import pytest

from utils.historical_daily_prices_helper import HistoricalDailyPricesHelper
from utils.strategy_backtester import StrategyBacktester


class DummySafePythonCodeExecutor:
    def check_and_compile(self, code: str):
        return compile(code, "<strategy>", "exec")

    def execute_compiled(self, compiled):
        ns = {}
        exec(compiled, ns, ns)
        return ns


@pytest.fixture()
def btc_csv_path(tmp_path):
    # 5 trading days
    df = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
            ),
            "Open":  [100, 110, 105, 120, 130],
            "High":  [110, 115, 120, 135, 140],
            "Low":   [95,  100, 100, 118, 125],
            "Close": [105, 107, 119, 130, 138],
            "Volume": [1, 1, 1, 1, 1],
        }
    ).set_index("Date")

    path = tmp_path / "btc.csv"
    df.to_csv(path, index=True)
    return str(path)


def make_helper_and_bt(csv_path: str):
 #   ex = DummySafePythonCodeExecutor()
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

    # On 2024-01-02 Open=110, buying 10000 BTC costs 1,100,000 USD -> should fail.
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
    # Buy executes at 2024-01-02 Open=110.
    # Day2 Low=100 triggers stop_loss=108 => sell at 108 => -2 USD.
    code = """\
def run(df, holdings):
    last_day = df.index[-1]
    if str(last_day.date()) == "2024-01-01":
        return [{"action": "BUY", "asset": "BTC", "amount": 1.0, "stop_loss": 108.0}]
    return []
"""
    res = bt.test_strategy("2024-01-02", "2024-01-02", code)

    assert not isinstance(res, str)
    assert res.total_portfolio_usd == pytest.approx(9998.0, abs=1e-6)
    assert res.revenue_percent == pytest.approx(-2.0 / 10000.0 * 100.0, abs=1e-6)


def test_multi_day_take_profit_and_stop_loss(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    # Multi-day strategy:
    # - On 2024-01-02: buy 1 BTC with take_profit=120 (no stop_loss)
    # - On 2024-01-04: buy 1 BTC with stop_loss=119 (will trigger same day because Low=118)
    #
    # Expected:
    # - First BTC bought at day2 Open=110; TP triggers day3 High=120; sell at 120 => +10
    # - Second BTC bought at day4 Open=120; SL triggers day4 Low=118; sell at 119 => -1
    # Net +9 => 10009
    code = """\
def run(df, holdings):
    last = str(df.index[-1].date())
    if last == "2024-01-01":
        return [{"action": "BUY", "asset": "BTC", "amount": 1.0, "take_profit": 120.0}]
    if last == "2024-01-03":
        return [{"action": "BUY", "asset": "BTC", "amount": 1.0, "stop_loss": 119.0}]
    return []
"""
    res = bt.test_strategy("2024-01-02", "2024-01-05", code)

    assert not isinstance(res, str)
    assert res.total_portfolio_usd == pytest.approx(10009.0, abs=1e-6)
    assert res.revenue_percent == pytest.approx(9.0 / 10000.0 * 100.0, abs=1e-6)

    # Both positions should be closed (TP then SL)
    assert sorted([h.asset for h in res.holdings]) == ["USD"]


def test_success_buy_then_sell_last_day_open(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    # Buy on 2024-01-02 (df last day 2024-01-01), sell on 2024-01-05 (df last day 2024-01-04).
    # Buy at day2 Open=110, sell at day5 Open=130 => +20
    code = """\
def run(df, holdings):
    last = str(df.index[-1].date())
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
    assert res.revenue_percent == pytest.approx(20.0 / 10000.0 * 100.0, abs=1e-6)
    assert sorted([h.asset for h in res.holdings]) == ["USD"]


def test_helper_function_allowed(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    code = """
def get_order():
    return [{"action": "BUY", "amount": 1.0, "asset": "BTC"}]
def run(df, holdings):
    return get_order()
"""
    print(code)
    res = bt.test_strategy("2024-01-02", "2024-01-05", code)
    assert not isinstance(res, str)
