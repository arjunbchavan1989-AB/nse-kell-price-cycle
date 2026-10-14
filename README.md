# NSE Oliver Kell Price Cycle

A daily price-cycle dashboard for the same eligible candidate universe as the NSE Stage Analysis dashboard. It implements transparent daily-bar approximations of the supplied Oliver Kell diagrams, not proprietary Kell formulas or trading advice.

## Dashboard

The daily-updating deployment is [NSE Price Cycle on GitHub Pages](https://arjunbchavan1989-ab.github.io/nse-kell-price-cycle/). Code and manual updates are available in the [public repository](https://github.com/arjunbchavan1989-AB/nse-kell-price-cycle) and its [Actions tab](https://github.com/arjunbchavan1989-AB/nse-kell-price-cycle/actions).

- **Cycle lanes:** Reversal Extension, Wedge Pop, EMA Crossback, Base 'n Break, Exhaustion Extension, Wedge Drop, bearish crossback and bearish base break, plus Trend / Holding and No Clear Setup.
- **Diagnostics:** 180 daily candlesticks, EMA10/20, volume, historical setup markers, reasons, signal age, and daily phase changes.
- **Relative strength:** 63 common-session excess return versus the exact Nifty MidSmallcap 400, then percentile ranking within the qualified scan.
- **TradingView:** Each column's Copy TV button copies all symbols currently matching its filters as comma-separated `NSE:SYMBOL` text. Paste into TradingView's Add symbols dialog; browsers cannot automatically paste into another website.
- **Controls:** Board/table views, direction, freshness, RS threshold, symbol search, sorting, CSV export, light/dark themes, and the supplied reference images.

The framework sequence and 10/20 EMA concepts follow the supplied images and [Deepvue's Oliver Kell overview](https://deepvue.com/screener/oliver-kell-screens/). Exact thresholds are implementation choices, exposed in `pipeline/cycle.py` and the dashboard's Scan rules dialog.

## Universe and sources

All comparisons are strict: market cap > ₹500 crore; 20-session average shares volume > 70,000; 20-session mean close × volume > ₹3 crore; 20-session average daily range percentage > 3%.

Range compatibility deliberately preserves the existing stage dashboard's calculation: mean(True Range / previous close × 100). This includes gaps and is not the gap-excluding mean((high − low) / close × 100) ADR convention.

Candidate membership and implied shares come from the existing [stage dashboard feed](https://arjunbchavan1989-ab.github.io/nse-stage-analysis/data/latest.json). This is not a fresh exhaustive NSE-wide market-cap census; stocks absent from that feed cannot enter this scanner. Market cap is re-marked using the source's market cap / close implied shares and the raw scan close. Price, liquidity, range, and benchmark calculations are anchored to that shared universe's session.

Equity OHLCV uses Yahoo Finance via yfinance. Benchmark closes use the exact named row in [NSE's index archive](https://archives.nseindia.com/content/indices/ind_close_all_13102026.csv); a different index is never substituted. The earlier migration to NSE-only equity prices remains paused. Technical OHLC prices are adjusted using Yahoo's Adj Close / Close factor; displayed latest close and liquidity filters use raw close.

## Daily automation

The GitHub Actions workflow runs Monday to Friday at **20:00 IST (14:30 UTC)**, after the existing universe's scheduled 19:00 IST refresh. GitHub scheduled runs may be delayed. Holidays have no new bars; the previous completed session remains visible. Actions also supports Run workflow manually.

At least 95% of source candidates must have histories for the same scan session. Snapshots older than four calendar days, stale source feeds, missing benchmark data, or empty universes fail the scan. Failed runs do not commit or deploy partial output and retain the last good published snapshot. A cached history speeds subsequent scans; no paid data keys or secrets are needed.

GitHub Pages deploys `web/` to the `gh-pages` branch. Repository Settings → Pages should select `gh-pages`, `/ (root)`. The public repository includes code, market-data snapshots, and the supplied reference images. Ensure any continued public redistribution of images/data complies with their owners' terms.

## Local commands

```bash
pip install -r pipeline/requirements.txt
python -m unittest discover -s tests -v
python pipeline/run.py
```

Serve `web/` with any static HTTP server. The production workflow uses Python 3.11. Engine parameters, including 3 ATR extensions, 1.2× breakout volume, prior 5-session pivots, 10-session base contraction, first crossback within 30 sessions, 100-bar warm-up, and five-session signal visibility, can be changed in `CONFIG`. Wedges are EMA/pivot proxies, not geometric trendline detection. Extension labels identify risk zones, not confirmed reversals.
