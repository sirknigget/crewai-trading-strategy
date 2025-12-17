import pandas as pd
import math

def calculate_ema(series, window):
    return series.ewm(span=window, adjust=False).mean()

def calculate_macd(df):
    close = df["Close"]
    ema12 = calculate_ema(close, 12)
    ema26 = calculate_ema(close, 26)
    macd = ema12 - ema26
    macd_signal = calculate_ema(macd, 9)
    return macd, macd_signal

def calculate_rsi(series, period):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def affordable_btc_amount(usd_amount, price):
    # Buy as much BTC as possible without exceeding available USD
    if price <= 0 or usd_amount <= 0:
        return 0.0
    qty = usd_amount / price
    est_cost = qty * price
    if est_cost > usd_amount:
        qty = math.floor((usd_amount / price) * 1e8) / 1e8  # trunc to 8 digits, conservative
        est_cost = qty * price
    if est_cost > usd_amount:
        qty -= 1e-8
    return max(0.0, qty)

def run(df, holdings):
    # Validate input
    if df is None or len(df) < 26:
        return []
    close = df["Close"]
    last_close = float(close.iloc[-1])
    macd, macd_signal = calculate_macd(df)
    rsi14 = calculate_rsi(close, 14)
    sma21 = close.rolling(window=21, min_periods=21).mean()

    # Extract final indicators
    last_macd = float(macd.iloc[-1])
    last_macd_signal = float(macd_signal.iloc[-1])
    last_rsi14 = float(rsi14.iloc[-1])
    last_sma21 = float(sma21.iloc[-1])

    # Portfolio state
    usd = next((h for h in holdings if h["asset"] == "USD"), None)
    btc_positions = [h for h in holdings if h["asset"] == "BTC"]
    orders = []

    # --- BUY logic ---
    # Buy if: no BTC held; MACD > signal; RSI > 50; above SMA21
    if usd is not None and not btc_positions:
        if (
            usd["amount"] > 0 and last_close > 0 and
            last_macd > last_macd_signal and
            last_rsi14 > 50 and
            last_close > last_sma21
        ):
            usd_avail = float(usd["amount"])
            buy_qty = affordable_btc_amount(usd_avail, last_close)
            if buy_qty > 0:
                stop_loss = round(last_close * 0.92, 2)  # -8%
                take_profit = round(last_close * 1.20, 2)  # +20%
                orders.append({
                    "action": "BUY",
                    "asset": "BTC",
                    "amount": float(buy_qty),
                    "stop_loss": stop_loss,
                    "take_profit": take_profit
                })

    # --- SELL logic ---
    # Exit BTC if: bear MACD/RSI/SMA21, or price hits stop/take-profit
    for h in btc_positions:
        sell = False
        # Indicator sell signals
        if last_macd < last_macd_signal or last_rsi14 < 50 or last_close < last_sma21:
            sell = True
        # Hard stop/take-profit checks if present
        h_tp = h.get("take_profit", None)
        h_sl = h.get("stop_loss", None)
        if h_tp is not None and last_close >= h_tp:
            sell = True
        if h_sl is not None and last_close <= h_sl:
            sell = True
        # Fallback stop/take-profit zones based on entry price
        entry = h.get("unit_value_usd", None)
        if entry is not None:
            if last_close >= 1.20 * entry:
                sell = True
            if last_close <= 0.92 * entry:
                sell = True
        # Place sell order if position open
        amt = float(h["amount"])
        if sell and amt > 0:
            orders.append({
                "action": "SELL",
                "holding_id": h["holding_id"],
                "amount": amt
            })
    return orders
