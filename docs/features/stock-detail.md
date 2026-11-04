# Stock detail

The `/stocks/:symbol` page lets a user choose among tracked companies and view crawled price history, quote tiles, a technical MASTER score, historical performance and quarterly valuation. It uses real crawled prices; missing inputs are displayed as unavailable rather than filled with estimates.

## Data shown

* **Quote tiles:** latest completed crawled session on or before yesterday in Asia/Kathmandu; includes OHLCV, previous crawled close, 52-week high / low, market cap and listed shares. Market cap needs `Company.listed_shares`.
* **Price chart:** up to the recent six months of daily crawled candles.
* **MASTER score:** a mechanical 0–100 score with weighted trend (35%), RSI momentum (25%), MACD (20%) and relative volume (20%). At least 200 crawled sessions are required. The response includes the score band, components and latest shareholding when available. This ranking is technical and is not investment advice.
* **Performance:** returns by trading-session windows, price ranges and averages, volume averages, one-month daily volatility and beta against NEPSE.
* **Valuation:** latest available quarterly report, with PE, PB, EPS, book value, DPPS and DPPS yields / averages. Calculation rules are documented in [quarterly-report](quarterly-report.md).

## API and access

All endpoints apply the user's company-access scope in addition to the listed permission.

| Method | Endpoint | Permission |
|---|---|---|
| `GET` | `/api/companies/<symbol>/quote/` | `view_price_history` |
| `GET` | `/api/companies/<id>/performance/` | `view_price_history` |
| `GET` | `/api/companies/<id>/master-score/` | `view_analysis` |
| `GET` | `/api/companies/<id>/valuation/` | `view_market_data` |

## Calculation limits

* Performance and MASTER score use raw crawled closes. Prices are not adjusted for bonus or right issues, so returns, beta and technical indicators spanning a corporate action can be distorted; see [status](../status.md).
* Beta uses dates present in both the stock's crawled prices and crawled NEPSE index history. It needs at least 30 return observations; fewer returns produce `insufficient_data`. A partial history is identified in the response.
* MASTER score requires 200 available sessions in its 420-calendar-day lookback. Its displayed as-of date is the last included crawled session.
* A missing quarterly filing or missing listed-share count leaves the corresponding valuation or market-cap fields unavailable.
