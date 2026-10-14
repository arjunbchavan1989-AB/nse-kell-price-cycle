# NSE Oliver Kell Price Cycle

A standalone daily price-cycle dashboard that builds its own NSE universe and downloads its own EOD prices and shares outstanding. It implements transparent daily-bar approximations of the supplied Oliver Kell diagrams, not proprietary Kell formulas or trading advice. No other dashboard feed or repository is needed.

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

The range calculation is mean(True Range / previous close × 100). This includes gaps and is not the gap-excluding mean((high − low) / close × 100) ADR convention.

Each run refreshes the official [NSE EQ listing](https://archives.nseindia.com/content/equities/EQUITY_L.csv), obtains its own Yahoo OHLCV histories and daily shares outstanding, and applies all four filters locally. Market cap is own shares × own raw EOD close. The latest completed session is checked against a dated NSE index archive before classification. No candidate membership, caps, prices or signals come from another dashboard. New eligible stocks can enter directly from the official listing.

Provider coverage is not an exhaustive market-cap census: unavailable Yahoo symbols and listings with fewer than 21 positive-volume bars cannot be evaluated. Snapshot diagnostics report official listing count, retrieved history count, missing symbols, same-session coverage and shares coverage. Under-65% broad listing/history coverage, under-95% same-session coverage among retrieved histories, or under-95% shares coverage among liquidity-qualified stocks stop publication. Eligible chart coverage is reported separately and must not be confused with broad listing coverage. Only this repository's caches are used.

Equity OHLCV uses Yahoo Finance via yfinance. Benchmark closes use the exact named row in [NSE's index archive](https://archives.nseindia.com/content/indices/ind_close_all_13102026.csv); a different index is never substituted. The earlier migration to NSE-only equity prices remains paused. Technical OHLC prices are adjusted using Yahoo's Adj Close / Close factor; displayed latest close and liquidity filters use raw close.

## Daily automation

The GitHub Actions workflow is scheduled **every day at 19:30 IST (14:00 UTC)**. It fetches its own inputs and updates independently of EP or any other dashboard. GitHub scheduled runs can be delayed; 19:30 is the scheduled start, not a guaranteed completion time. Weekends and holidays have no new bars; the previous completed session remains visible. Actions supports Run workflow manually at any time; before 19:00 IST the scanner uses the previous completed session.

No paid data key, cross-repository token or upstream workflow is required.
`refresh_data=false` remains available for UI-only deployment.
The GitHub Pages and preview/pplx app frontends read this dashboard's own public
`main/web/data/` via GitHub Raw, with minute-level cache keys, so daily updates
appear without relying on Pages data-cache expiry. Current snapshots must carry
independent-acquisition provenance; old dependent snapshots are rejected. If the
initial remote fetch fails, a verified independent bundled last-good snapshot
is used consistently, with EOD/generation timestamps visible. Live and bundled
chart files are not mixed.

At least 95% of independently qualified candidates must have histories for the same scan session. Snapshots older than four calendar days, missing benchmark data, or empty universes fail the scan. Failed runs do not commit or deploy partial output and retain the last good published snapshot. An own-repository cache speeds subsequent scans.

GitHub's native Pages actions configure, upload and deploy a validated `web/` artifact. Repository Settings → Pages uses **GitHub Actions** as its build source (configured for the live repository). Publication is verified inside the daily workflow, so a failed deployment cannot leave the scan green while a separate legacy branch build fails. The public repository includes code, market-data snapshots, and the supplied reference images. Ensure any continued public redistribution of images/data complies with their owners' terms.

## Local commands

```bash
pip install -r pipeline/requirements.txt
python -m unittest discover -s tests -v
python pipeline/run.py
```

Serve `web/` with any static HTTP server. The production workflow uses Python 3.11. Engine parameters, including 3 ATR extensions, 1.2× breakout volume, prior 5-session pivots, 10-session base contraction, first crossback within 30 sessions, 100-bar warm-up, and five-session signal visibility, can be changed in `CONFIG`. Wedges are EMA/pivot proxies, not geometric trendline detection. Extension labels identify risk zones, not confirmed reversals.
