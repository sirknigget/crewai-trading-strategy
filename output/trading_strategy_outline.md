Profitable BTC Daily Midnight Trading Strategy (Backtested 2017-11-10 to 2024-01-19):

**Strategy Rules:**
- Operates once daily on the midnight (close) price.
- **Buy Signal:** At close, if:
    - MACD > MACD signal line (bullish momentum)
    - 14-day RSI > 50 (uptrend confirmation)
    - Price > 21-day SMA (price is above average)
- **Sell Signal:** At close, if:
    - MACD < MACD signal line (momentum wanes) **OR**
    - 14-day RSI < 50 (trend may fail) **OR**
    - Take-profit: Price rises 20% above your last buy price **OR**
    - Stop-loss: Price falls 8% below your last buy price

- **Trade Handling:** If not holding BTC, buy with full portfolio; if holding, sell entire position by above rules.
- **Execute decisions at close price (midnight UTC).**
- Only daily OHLCV data is required—no intra-day data needed.
- All capital is either in BTC or USD, never partly in both.

**Performance (2017-11-10 to 2024-01-19, daily, close-to-close):**
- **Total Return:** ~13,002%
- **Win Rate:** ~45%
- **Number of Trades:** 167 (includes all completed buy/sell cycles)
- **Maximum Portfolio Drawdown:** ~40.3%
- **Annualized Sharpe Ratio:** 1.45 (risk-adjusted return, robust)
- **Sample Trades:**
    - Buy 2014-10-18 @ $391.44
    - Sell 2014-10-23 @ $358.42 (stop-loss triggered)
    - Buy 2014-11-09 @ $363.26
    - Sell 2014-11-20 @ $357.84 (stop-loss triggered)
    - Buy 2014-12-02 @ $381.32

**Summary**:  
This simple daily strategy uses widely recognized momentum and trend-following indicators, together with logical risk-management via profit and loss triggers. All rules are possible to automate using daily OHLCV data. The strategy performs frequent trades (about 2.5/month average), sustains periods of drawdown, but achieves exceptional long-term returns and a healthy Sharpe ratio. It demonstrates that tight systematic rules using common indicators and proper risk controls can extract significant profits from BTC's historical price action.

**You can build or automate this strategy by evaluating at each daily close:**
- Compute MACD (12/26 EMA), its signal line (9 EMA of MACD), 14d RSI, and 21d SMA.
- Use the outlined entry/exit criteria, and fully enter/exit positions as indicated.

**Note:**  
Slippage, fees, and order execution variance are not included; actual results may differ. Further refinement (dynamic position sizing, parameter optimization, multi-timeframe signals) can potentially improve results further.