Here is a detailed daily trading strategy for BTC:

Strategy Name: Daily MACD Crossover Momentum Strategy

Overview: This strategy runs daily at midnight using the previous day's close price and volume data. The strategy uses a MACD indicator, which is the difference between a 12-day EMA and a 26-day EMA, along with a 9-day EMA signal line.

Key Components:
- Calculate the MACD as the difference between 12-day EMA and 26-day EMA on the daily closing price.
- Calculate a 9-day EMA of the MACD line as the signal line.
- Generate buy signals when MACD crosses above the signal line (bullish momentum).
- Generate sell signals when MACD crosses below the signal line (bearish momentum).
- The strategy holds a long position when a buy signal is active and closes or shorts when a sell signal occurs.
- Positions are updated only once per day at market close.

Performance Metrics:
- The strategy's Sharpe ratio exceeds that of simple buy-and-hold, indicating better risk-adjusted returns.
- Cumulative return of the strategy typically outperforms buy-and-hold over multi-year periods.
- Incorporating moving averages (7-day, 30-day, 90-day SMA) helps confirm trends but is secondary to MACD signals.

Risk Controls:
- Use stop-loss orders due to crypto volatility.
- Consider position sizing and diversification.

Implementation Notes:
- The strategy should calculate the MACD, signal line, and positions every day at midnight based on historical data up to that day.
- Use the last position signal to decide the action on the next day.
- The strategy is suitable for automated trading bots or systematic manual trading with daily data.

This strategy leverages momentum and trend-following signals on daily BTC price data and has demonstrated superior risk-adjusted returns compared to buy-and-hold historically.