def get_strategy_code_guidelines() -> str:
    return """Write a single self-contained Python code snippet that defines a TOP-LEVEL function named `run` with this exact signature:

    def run(df, holdings):
        ...

This code represents a real-world trading strategy that makes decisions using ONLY the provided inputs and returns a list of orders to execute.

INPUTS
1) df (pandas.DataFrame)
- Daily OHLCV time series.
- Index: date-like (DatetimeIndex).
- Columns: Open, High, Low, Close, Volume.
- IMPORTANT: df contains only historical data available BEFORE the current execution time (no future/current candle data).

2) holdings (list[dict])
A list of current portfolio holdings. Each holding dict has:
- holding_id: str (unique identifier). The USD cash position uses holding_id == "USD".
- asset: str (currently "USD" or "BTC").
- amount: float (units of the asset).
- unit_value_usd: float (USD is always 1.0; BTC is the latest known BTC unit price in USD based on available historical data).
- total_value_usd: float (amount * unit_value_usd).
- stop_loss: float | None (optional unit-price threshold in USD for the holding).
- take_profit: float | None (optional unit-price threshold in USD for the holding).

RETURN VALUE
Return a list of order dictionaries (or an empty list if no actions). Orders are executed in the exact order returned.

Each order MUST match one of these schemas:

A) BUY order
{
  "action": "BUY",
  "asset": "BTC",                 # currently only BTC is supported for buys
  "amount": float,                # BTC units to buy (must be > 0)
  "stop_loss": float | None,      # optional BTC unit-price threshold in USD
  "take_profit": float | None     # optional BTC unit-price threshold in USD
}

B) SELL order
{
  "action": "SELL",
  "holding_id": str,              # must refer to an existing BTC holding_id from `holdings`
  "amount": float                 # BTC units to sell from that holding (must be > 0)
}

RULES / CONSTRAINTS
- Define `run(df, holdings)` at top level (not nested in a class).
- Helper functions are allowed, but keep everything in this single snippet.
- Do not perform I/O: no file reads/writes, no network calls, no database access.
- Do not rely on global state, environment variables, or system time.
- Do not print/log; just compute and return orders.
- Return only JSON-serializable values: dict/list/str/float/int/None.
- Be robust to short history: if df has too few rows for an indicator, return [].

PRACTICAL GUIDANCE
- Use df["Close"].iloc[-1] as the last known close price.
- Use holdings to determine available cash (USD holding) and open BTC positions.
- If selling, choose the correct holding_id and ensure the amount does not exceed that holding's amount.
- If buying, choose a BTC amount that is affordable given the USD holding.
- Place orders in the exact sequence they should execute.

EXAMPLE SKELETON (edit into your strategy)

import pandas as pd

def run(df, holdings):
    # Return no orders until enough candles exist
    if df is None or len(df) < 20:
        return []

    last_close = float(df["Close"].iloc[-1])
    sma20 = float(df["Close"].tail(20).mean())

    usd = next(h for h in holdings if h["asset"] == "USD")
    btc_positions = [h for h in holdings if h["asset"] == "BTC"]

    orders = []

    # Example: enter if trend up and no BTC position
    if last_close > sma20 and not btc_positions:
        # example sizing: spend up to 10% of USD
        budget = float(usd["amount"]) * 0.10
        if budget > 0 and last_close > 0:
            qty = budget / last_close
            orders.append({
                "action": "BUY",
                "asset": "BTC",
                "amount": float(qty),
                "stop_loss": None,
                "take_profit": None,
            })

    # Example: exit if trend down (sell full first BTC holding)
    if last_close < sma20 and btc_positions:
        h = btc_positions[0]
        orders.append({
            "action": "SELL",
            "holding_id": h["holding_id"],
            "amount": float(h["amount"]),
        })

    return orders
"""