# tests/test_strategy_backtester.py
import pandas as pd
import pytest

from utils.historical_daily_prices_helper import HistoricalDailyPricesHelper
from utils.strategy_backtester import StrategyBacktester


#
# class DummySafePythonCodeExecutor:
#     def check_and_compile(self, code: str):
#         return compile(code, "<strategy>", "exec")
#
#     def execute_compiled(self, compiled):
#         ns = {}
#         exec(compiled, ns, ns)
#         return ns
#

@pytest.fixture()
def btc_csv_path(tmp_path):
    # 5 trading days
    df = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
            ),
            "Open": [100, 110, 105, 120, 130],
            "High": [110, 115, 120, 135, 140],
            "Low":  [95,  100, 100, 118, 125],
            "Close":[105, 107, 119, 130, 138],
            "Volume": [1, 1, 1, 1, 1],
        }
    ).set_index("Date")

    path = tmp_path / "btc.csv"
    df.to_csv(path, index=True)
    return str(path)


def make_helper_and_bt(csv_path: str):
   # ex = DummySafePythonCodeExecutor()
    helper = HistoricalDailyPricesHelper(csv_path)
    bt = StrategyBacktester(helper)
    return helper, bt


def test_date_range_out_of_bounds(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    code = "def run(df, holdings):\n    return []\n"
    res = bt.test_strategy("2023-12-01", "2024-01-03", code)
    assert isinstance(res, str)
    assert "Date range validation error" in res


def test_missing_run_function(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    code = "def not_run(df, holdings):\n    return []\n"
    res = bt.test_strategy("2024-01-01", "2024-01-03", code)
    assert isinstance(res, str)
    assert "Strategy code validation error" in res
    assert "run(df, holdings)" in res


def test_order_overspend_error(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    # Tries to buy 10_000 BTC at close ~105 => massive overspend
    code = """\
def run(df, holdings):
    # Always buy absurd amount
    return [{"action": "BUY", "asset": "BTC", "amount": 10000.0}]
"""
    res = bt.test_strategy("2024-01-01", "2024-01-01", code)
    assert isinstance(res, str)
    assert "Order error: Insufficient USD for BUY" in res


def test_sell_nonexistent_holding_id(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    code = """\
def run(df, holdings):
    return [{"action": "SELL", "holding_id": "H999", "amount": 1.0}]
"""
    res = bt.test_strategy("2024-01-01", "2024-01-01", code)
    assert isinstance(res, str)
    assert "Order error: SELL refers to non-existing holding_id" in res


def test_success_buy_then_sell_end(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    # Buy 1 BTC on first day, sell it on last day.
    code = """\
def run(df, holdings):
    # df includes data until "today"
    today = df.index[-1]
    # naive: buy on first dataset day, sell on last day of the full fixture
    if str(today.date()) == "2024-01-01":
        return [{"action": "BUY", "asset": "BTC", "amount": 1.0}]
    if str(today.date()) == "2024-01-05":
        # find first BTC holding
        for h in holdings:
            if h["asset"] == "BTC":
                return [{"action": "SELL", "holding_id": h["holding_id"], "amount": h["amount"]}]
    return []
"""
    res = bt.test_strategy("2024-01-01", "2024-01-05", code)
    assert not isinstance(res, str)

    # After buy at 105 and sell at 138 => +33 USD profit on 1 BTC
    assert res.total_portfolio_usd == pytest.approx(10000.0 + 33.0, abs=1e-6)
    assert res.revenue_percent == pytest.approx(33.0 / 10000.0 * 100.0, abs=1e-6)

    # Ensure only USD holding remains (BTC should be sold out)
    assets = sorted([h.asset for h in res.holdings])
    assert assets == ["USD"]


def test_stop_loss_triggers_autosell(btc_csv_path):
    _, bt = make_helper_and_bt(btc_csv_path)

    # Buy 1 BTC with stop_loss at 102 on day 1.
    # Day1 Low is 95, so stop-loss triggers immediately (autosell at 102).
    code = """\
def run(df, holdings):
    today = df.index[-1]
    if str(today.date()) == "2024-01-01":
        return [{"action": "BUY", "asset": "BTC", "amount": 1.0, "stop_loss": 102.0}]
    return []
"""
    res = bt.test_strategy("2024-01-01", "2024-01-01", code)
    assert not isinstance(res, str)

    # Buy at Close=105, then stop-loss sells at 102 => -3 USD
    assert res.total_portfolio_usd == pytest.approx(9997.0, abs=1e-6)
    assert res.revenue_percent == pytest.approx(-3.0 / 10000.0 * 100.0, abs=1e-6)
