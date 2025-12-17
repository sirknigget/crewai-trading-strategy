# Detailed Design Document for BTC Daily Trading Strategy Implementation

## 1. Strategy Logic Description

This trading strategy aims to capture profitable trades on BTC by combining trend-following and momentum indicators evaluated on daily closing prices. It operates using only historical data available up to, but not including, the current day’s close. The logic is as follows:

- **Indicators Computed Daily:**
  - 10-day Simple Moving Average (SMA10) of Close price (fast SMA)
  - 50-day Simple Moving Average (SMA50) of Close price (slow SMA)
  - 14-day Relative Strength Index (RSI) of Close price
  - MACD line computed as difference between 12-day EMA and 26-day EMA on Close price
  - MACD signal line computed as 9-day EMA of MACD line
  - MACD crossover signals identified by comparing previous day and current day MACD line vs signal line relations

- **Entry (Buy) Conditions:**
  - Current day’s SMA10 is strictly above SMA50 → indicates upward trend
  - Current day’s RSI < 30 → oversold condition, suggests potential bounce
  - Current day’s MACD line crosses above the MACD signal line → bullish momentum shift

  If all three conditions are met on a given daily close and there is currently no BTC holding, the strategy buys BTC using ALL available USD cash in portfolio at the current closing price.

- **Exit (Sell) Conditions:**
  - Any one of the following is true on current daily close:
    - SMA10 falls below SMA50 → trend reversal signal
    - RSI rises above 70 → overbought signal
    - MACD line crosses below the MACD signal line → bearish momentum signal

  If any exit condition is met and the strategy has an open BTC position, it sells the full BTC position at the current close price, converting BTC back to USD.

- **Position Management Constraints:**
  - Positions are all or nothing: either full cash or full BTC; no partial trades.
  - Trades are executed only at the daily close price.
  - Stop loss and take profit indicators are not explicitly stated for this version and will be set to None.
  - The strategy is robust to data scarcity by requiring enough data to compute all indicators; if insufficient data is present, no trades are made.
  - The holding list is used to determine current cash and BTC status. The USD holding has `holding_id == "USD"`. BTC holdings (if any) are identified from holdings list by `asset == "BTC"`.

## 2. Function and Method Signatures

The top-level interface method required by the trading system is:

```python
def run(df: pd.DataFrame, holdings: list[dict]) -> list[dict]:
    """
    df: DataFrame with columns ["Date", "Open", "High", "Low", "Close", "Volume"] sorted ascending by date.
    holdings: current holdings list as per system API.

    Returns:
        List of order dicts (BUY or SELL orders) or empty list if no trade.
    """
```

Helper functions (all internal to the single code snippet) include:

- `calculate_sma(series: pd.Series, window: int) -> pd.Series`
- `calculate_ema(series: pd.Series, span: int) -> pd.Series`
- `calculate_rsi(series: pd.Series, period: int) -> pd.Series`
- `calculate_macd(series: pd.Series) -> tuple(pd.Series, pd.Series)`  
  Returns MACD line and MACD signal line
- `detect_macd_cross(macd_line: pd.Series, signal_line: pd.Series) -> tuple[bool, bool]`  
  Returns `(cross_above, cross_below)` booleans for latest day

## 3. Data Structures

- Input `df`: pandas DataFrame as described.
- Input `holdings`: list of dict, each dict contains at least:
  - `holding_id`: str
  - `asset`: str ("USD" or "BTC")
  - `amount`: float
  - `unit_value_usd`: float
  - `total_value_usd`: float
  - optional fields: `stop_loss`, `take_profit` (both float or None)

- Output `orders`: list of dict with schema:

  **BUY order:**

  ```python
  {
    "action": "BUY",
    "asset": "BTC",
    "amount": float,         # BTC units > 0
    "stop_loss": None,
    "take_profit": None
  }
  ```

  **SELL order:**

  ```python
  {
    "action": "SELL",
    "holding_id": str,       # from BTC holding_id in holdings
    "amount": float         # BTC units > 0 and <= holding amount
  }
  ```

## 4. Pseudocode for Main Algorithm

```plaintext
function run(df, holdings):
    if df is None or len(df) < 50 + 14:  # require enough to calculate all indicators
        return []

    Extract Close price series from df

    Compute SMA10 and SMA50 on Close
    Compute RSI14 on Close
    Compute MACD line and MACD signal line on Close

    Identify MACD crossover signals on last day (day -1):
        cross_above = MACD line crossed above signal line today
        cross_below = MACD line crossed below signal line today

    Extract last day's indicators:
        last_sma10 = SMA10 at last day
        last_sma50 = SMA50 at last day
        last_rsi = RSI14 at last day

    Get USD holding (amount, total_value), BTC holdings (list)

    Determine current position:
        if BTC holdings is empty => position = "cash"
        else => position = "btc"

    Initialize empty list orders

    # Entry condition (buy)
    if position == "cash":
        if last_sma10 > last_sma50 and last_rsi < 30 and cross_above:
            available_usd = USD holding.amount
            if available_usd > 0 and last_close > 0:
                btc_qty = available_usd / last_close
                create BUY order with btc_qty, stop_loss=None, take_profit=None
                add order to orders

    # Exit condition (sell)
    if position == "btc":
        if last_sma10 < last_sma50 or last_rsi > 70 or cross_below:
            # Sell entire BTC holdings (only one holding assumed or aggregate all)
            for each btc holding in btc holdings:
                sell amount = holding.amount
                create SELL order with holding_id and sell amount
                add order to orders
            # strategy fully sells all BTC positions, so loop through all holdings

    return orders
```

---

# Complete Design Summary

- Uses standard, well-known indicator formulas.
- Uses only available historical data before current execution (no lookahead).
- Detects MACD crosses by comparing prior day to current day.
- Buys entire available cash amounts into BTC when entry conditions met.
- Sells entire BTC position when exit conditions met.
- Returns list of orders in correct execution order.
- Returns empty list if no trade.
- Robust to data insufficiency.
- No intra-day or partial trades.
- No external dependencies beyond `pandas`.

---

# Next Step: Implementation based on this design.

This detailed design enables a developer to implement the strategy in a single Python code snippet that calculates indicators, checks signals, manages positions, and produces the correct trading orders conforming to the specified API. The pseudocode guides the control flow, and the signatures define all required helper functions.

This concludes the detailed design requested.