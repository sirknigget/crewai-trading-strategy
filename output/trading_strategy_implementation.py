import pandas as pd

def calculate_sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()

def calculate_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def calculate_rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    # Use Wilder's smoothing after initial average
    avg_gain = avg_gain.combine_first(gain.ewm(alpha=1/period, adjust=False).mean())
    avg_loss = avg_loss.combine_first(loss.ewm(alpha=1/period, adjust=False).mean())

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(series: pd.Series) -> tuple:
    ema12 = calculate_ema(series, 12)
    ema26 = calculate_ema(series, 26)
    macd_line = ema12 - ema26
    signal_line = calculate_ema(macd_line, 9)
    return macd_line, signal_line

def detect_macd_cross(macd_line: pd.Series, signal_line: pd.Series) -> tuple:
    # Need at least two points to detect cross
    if len(macd_line) < 2 or len(signal_line) < 2:
        return False, False

    prev_macd = macd_line.iloc[-2]
    prev_signal = signal_line.iloc[-2]
    curr_macd = macd_line.iloc[-1]
    curr_signal = signal_line.iloc[-1]

    cross_above = (prev_macd <= prev_signal) and (curr_macd > curr_signal)
    cross_below = (prev_macd >= prev_signal) and (curr_macd < curr_signal)

    return cross_above, cross_below

def run(df, holdings):
    # Return empty if data or holdings is None
    if df is None or holdings is None:
        return []

    # Require at least max window for indicators plus 1 for MACD cross
    required_len = 50 + 14 + 1
    if len(df) < required_len:
        return []

    close = df["Close"]

    sma10 = calculate_sma(close, 10)
    sma50 = calculate_sma(close, 50)
    rsi14 = calculate_rsi(close, 14)
    macd_line, signal_line = calculate_macd(close)

    cross_above, cross_below = detect_macd_cross(macd_line, signal_line)

    last_sma10 = sma10.iloc[-1]
    last_sma50 = sma50.iloc[-1]
    last_rsi = rsi14.iloc[-1]
    last_close = float(close.iloc[-1])

    # Validate last SMA and RSI values to be not nan
    if pd.isna(last_sma10) or pd.isna(last_sma50) or pd.isna(last_rsi):
        return []

    # Find USD holding
    usd_holding = None
    btc_holdings = []
    for h in holdings:
        if h.get("asset") == "USD" and h.get("holding_id", "") == "USD":
            usd_holding = h
        elif h.get("asset") == "BTC" and h.get("holding_id") is not None:
            btc_holdings.append(h)

    usd_amount = float(usd_holding.get("amount", 0.0)) if usd_holding else 0.0

    orders = []

    # Position state
    has_btc = len(btc_holdings) > 0

    # Entry condition (BUY)
    if not has_btc:
        if last_sma10 > last_sma50 and last_rsi < 30 and cross_above:
            available_usd = usd_amount
            if available_usd > 0 and last_close > 0:
                btc_qty = available_usd / last_close
                if btc_qty > 0:
                    orders.append({
                        "action": "BUY",
                        "asset": "BTC",
                        "amount": float(btc_qty),
                        "stop_loss": None,
                        "take_profit": None
                    })

    # Exit condition (SELL all BTC holdings)
    if has_btc:
        if last_sma10 < last_sma50 or last_rsi > 70 or cross_below:
            for h in btc_holdings:
                amt = float(h.get("amount", 0.0))
                hid = h.get("holding_id")
                if amt > 0 and hid is not None:
                    orders.append({
                        "action": "SELL",
                        "holding_id": hid,
                        "amount": amt
                    })

    return orders
