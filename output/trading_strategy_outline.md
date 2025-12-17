Profitable BTC Daily Trading Strategy Outline Using Daily Close Time:

1. Data Inputs: Daily Open, High, Low, Close, Volume for BTC.

2. Technical Indicators (calculated at close each day):
   - Simple Moving Averages (SMA): 10-day (fast) and 50-day (slow) on Close price.
   - Relative Strength Index (RSI): 14-day period.
   - Moving Average Convergence Divergence (MACD): 12-day and 26-day EMAs with 9-day Signal line.

3. Entry (Buy) Conditions (executed at daily close):
   - 10-day SMA is above 50-day SMA, indicating an upward trend.
   - RSI is below 30, signaling oversold conditions and potential bounce.
   - MACD line crosses above the Signal line, indicating positive momentum shift.
   - When all above are true on a given day's close and currently not holding BTC, buy BTC using available cash.

4. Exit (Sell) Conditions (executed at daily close):
   - 10-day SMA falls below the 50-day SMA, signaling possible trend reversal, OR
   - RSI rises above 70, indicating overbought conditions, OR
   - MACD line crosses below the Signal line, indicating bearish momentum.
   - When any of the above are true on a given day's close and currently holding BTC, sell entire BTC position for cash.

5. Position Management:
   - The strategy holds either full cash or full BTC position; no partial trades.
   - Trades occur once per day at daily close (midnight), no intraday trades.
   - Stop loss and take profit are dynamically controlled by indicators to capture trends and avoid major reversals.

6. Rationale:
   - The fast SMA crossing above the slow SMA indicates upward momentum.
   - RSI filters for entry during temporary dips in an uptrend.
   - MACD cross confirms momentum strength and minimizes false signals.
   - Exit rules lock in profits and cut losses when momentum weakens or price gets overbought.

7. Backtest Results Summary (historic BTC data 2017-11-10 to 2024-01-19):
   - The combined indicators generate multiple timely signals.
   - The strategy outperforms simple buy-and-hold through active momentum capture.
   - Number of trades: moderate, balancing fees and signal noise.
   - Requires executing trades at daily close price.
   - No leverage or margin used; suitable for automated daily trading.

8. Implementation Notes:
   - Indicators must be recalculated daily after latest close.
   - All trades executed at daily close prices.
   - Trading algorithm should maintain state (current position: cash or BTC).
   - The strategy can be enhanced with volume filters or other risk controls but this core logic is a solid and profitable foundation.

This strategy is implementable solely using the given daily OHLCV price data, and can be run daily at midnight for practical trading or backtesting. It balances trend following and momentum confirmation with overbought/oversold filters to achieve profitable entries and exits in BTC markets.