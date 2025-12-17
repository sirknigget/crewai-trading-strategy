---
# Detailed Technical Design: BTC Daily Midnight Momentum Strategy

## 1. Strategy Logic Overview

- **Trade Timing:** Evaluated once daily at the close (end of day close in OHLCV).
- **Entry (Buy) Criteria:**  
  * Enter (buy with all USD) if ALL the following:
    1. MACD (12 EMA – 26 EMA) > MACD Signal Line (9 EMA of MACD)
    2. 14-day RSI > 50
    3. Close > 21-day SMA

- **Exit (Sell) Criteria:**  
  * Exit (sell all BTC) if ANY of the following:
    1. MACD < MACD Signal Line
    2. 14-day RSI < 50
    3. Close >= 1.20 × last buy price (take profit)
    4. Close <= 0.92 × last buy price (stop loss)

- **Trade Management:**  
  * Invest 100% in either USD or BTC, never both. On buy, use all USD. On sell, clear all BTC.
  * Set stop-loss and take-profit with the respective price levels for BTC buys.
  * All signals are checked at latest available close in `df`.

---

## 2. Function and Method Signatures

- **Main Entrypoint**:  
  ```python
  def run(df, holdings):
      ...
  ```

- **Indicators/Helpers**:  
  ```python
  def calculate_ema(series: pd.Series, window: int) -> pd.Series

  def calculate_macd(df: pd.DataFrame) -> (pd.Series, pd.Series)
      # Returns: (macd_series, macd_signal_series)

  def calculate_rsi(series: pd.Series, period: int) -> pd.Series

  def get_usd_holding(holdings: list[dict]) -> dict

  def get_btc_holding(holdings: list[dict]) -> dict | None

  def get_last_btc_buy_price(holdings: list[dict]) -> float | None
  ```

- **Order Construction**:  
  Orders are returned as per required schemas:
    - Buy order dict per spec ("action": "BUY", ...)
    - Sell order dict per spec ("action": "SELL", ...)

---

## 3. Data Structures

- **Inputs:**
  - **df (pandas.DataFrame):**  
    Must include at least 26 rows for MACD, 21 for SMA, 14 for RSI. Columns are "Open", "High", "Low", "Close", "Volume".

  - **holdings (list[dict])**  
    Tracks current USD and BTC holdings, including:
    - `holding_id` (str)
    - `asset` ("USD" or "BTC")
    - `amount` (float)
    - `unit_value_usd` (value/unit at last close)
    - `stop_loss`, `take_profit` (floats, for BTC entries)

- **Indicators:** (pandas.Series or float)
    - 12 EMA, 26 EMA (for MACD)
    - MACD, MACD Signal (9 EMA of MACD)
    - 14-day RSI
    - 21-day SMA

---

## 4. Pseudocode Algorithm

```plaintext
run(df, holdings):
    # Ensure enough data for all indicators
    if df is None or len(df) < 26:
        return []

    # Compute indicators
    close = df["Close"]
    macd, macd_signal = calculate_macd(df)
    rsi14 = calculate_rsi(close, 14)
    sma21 = close.rolling(21).mean()

    # Only look at the last value
    last_close = float(close.iloc[-1])
    last_macd = float(macd.iloc[-1])
    last_macd_signal = float(macd_signal.iloc[-1])
    last_rsi14 = float(rsi14.iloc[-1])
    last_sma21 = float(sma21.iloc[-1])

    # Gather holdings
    usd_holding = get_usd_holding(holdings)
    btc_holding = get_btc_holding(holdings)
    last_btc_buy_price = get_last_btc_buy_price(holdings)  # Use "unit_value_usd" from BTC holding

    orders = []

    if btc_holding is None:
        # Only enter if all buy signals
        if (last_macd > last_macd_signal) and (last_rsi14 > 50) and (last_close > last_sma21):
            buy_amount = usd_holding["amount"] / last_close
            take_profit = round(last_close * 1.20, 2)
            stop_loss = round(last_close * 0.92, 2)
            orders.append({
                "action": "BUY",
                "asset": "BTC",
                "amount": float(buy_amount),
                "stop_loss": stop_loss,
                "take_profit": take_profit,
            })
    else:
        # Determine if any sell conditions trigger
        sell = False
        sell_reasons = []
        if last_macd < last_macd_signal:
            sell = True
            sell_reasons.append("MACD")
        if last_rsi14 < 50:
            sell = True
            sell_reasons.append("RSI")
        if last_btc_buy_price is not None:
            if last_close >= last_btc_buy_price * 1.20:
                sell = True
                sell_reasons.append("Take-profit")
            if last_close <= last_btc_buy_price * 0.92:
                sell = True
                sell_reasons.append("Stop-loss")
        if sell:
            orders.append({
                "action": "SELL",
                "holding_id": btc_holding["holding_id"],
                "amount": float(btc_holding["amount"]),
            })
    return orders
```

#### Indicator Calculations:

- **EMA Calculation**: Use pandas.Series.ewm(span=N, adjust=False).mean()
- **MACD**: 12 EMA minus 26 EMA; MACD Signal is 9 EMA of MACD.
- **RSI**: Use standard 14-period RSI (calculate up/down changes, compute average gain/loss, derive RSI).
- **SMA**: Use pandas.Series.rolling(window=N).mean()

#### Note on Holdings:
- The BTC "holding" includes "unit_value_usd" which is used as last buy price for stop-loss/take-profit. If not present (older code), fall back to None.

---

## Implementation Notes

- All calculations must only use data available up to the penultimate close (NO lookahead).
- All orders are placed in full (all-in/all-out, per capital available).
- The strategy never leaves the portfolio partly in USD, partly in BTC — it's always one or the other.
- The main `run(df, holdings)` function is top-level, with helpers allowed but NOT nested inside class.
- No I/O, no reliance on anything except passed-in parameters.

---

## Example Data Flow

| Signal Condition      | Portfolio State | Action            | Order Output                    |
|----------------------|-----------------|-------------------|----------------------------------|
| All buy triggers met | USD only        | Enter BTC         | BUY (all USD → BTC; set TP/SL)   |
| Any sell trigger met | BTC only        | Exit to USD       | SELL (all BTC; refer holding_id) |
| None trigger         | Any             | Hold/no action    | []                               |

---

## Summary Table: Indicator Calculation Windows

| Indicator | Window/Period | Data Required (rows) |
|-----------|--------------|----------------------|
| EMA 12    | 12           | 12                   |
| EMA 26    | 26           | 26                   |
| MACD Sig  | 9 EMA of MACD| 26 (+9)              |
| 14d RSI   | 14           | 14                   |
| 21d SMA   | 21           | 21                   |

*The minimum rows needed is 26 (for MACD start). If not, return no orders.*

---

# Developer Ready Summary

To implement:

1. At each call to `run(df, holdings)`, ensure at least 26 rows in `df`. If not, return [].
2. Compute indicators (MACD, MACD signal, 14d RSI, 21d SMA) at the latest close.
3. If no BTC held: If all buy criteria true, BUY full USD amount of BTC, set stop-loss/take-profit.
4. If holding BTC: If any sell criterion true (indicator or price-based), SELL all BTC from that holding.
5. Return all orders in correct format as required.
6. All indicator and accounting logic is robust to missing/insufficient data.
7. Use latest close price for sizing, never exceeds available USD/BTC.
8. Do not perform I/O, do not print/log, do not use global/mutable state.

---

This design provides everything needed for a developer to implement the `run(df, holdings)` trading strategy function, fully compliant with provided system and strategy rules.