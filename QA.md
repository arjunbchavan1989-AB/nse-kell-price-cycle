# Verification inventory

## Scanner

- Wilder ATR seed and recursion; breakout pivots and volume references exclude the current bar.
- Flat and short-history stocks remain unclassified; upside/downside extensions have distinct labels.
- Prefix indicator results do not change when future bars are appended.
- RS requires 64 common sessions and uses the same benchmark session.
- Source universe metadata matches the four strict filters.
- At least 95% same-session coverage; no mixed-session breadth; empty/stale scans fail.
- Latest snapshot has all filter values above thresholds, phase totals equal row count, unique symbols, and a chart file for every row.

## Browser controls

- Desktop 1440 × 900 and mobile 390 × 844: initial summary, filter toolbar, horizontally scrollable phase lanes, no page-level horizontal overflow.
- Board/table toggle and return; each phase selector toggles on/off.
- Symbol search: known symbol and no-results input, then reset.
- Direction, freshness, RS minimum and all four sort options.
- Per-column Copy TV equals the filtered lane's complete unique `NSE:SYMBOL` list; empty lanes disable copy. Single-symbol copy matches the chart symbol.
- Stock detail: chart loads, 60/120/180-bar ranges, hover OHLC/volume, metrics, reasons, event badges, Escape/close.
- CSV export downloads current filtered rows.
- Scan rules and both uploaded reference images load and close.
- Light/dark round trip; chart redraws.
- Off-happy-path: impossible search produces a genuine empty state; missing snapshot/chart displays an honest error rather than fabricated results.

## Deployment

- Public GitHub repository has workflow and initial genuine snapshot.
- Scheduled UTC cron corresponds to 20:00 IST; manual dispatch available.
- First hosted pipeline run succeeds and creates the gh-pages branch.
- GitHub Pages live index and JSON are reachable and match committed output.
- The separate Perplexity preview is a captured snapshot; GitHub Pages is the daily-updating deployment.

## Local results, 14 October 2026

Twelve regression tests passed, including publication guards that preserve a sentinel last-good snapshot on insufficient coverage or a price/universe session mismatch. The initial scan covers 849/849 source candidates for the shared universe's 12 October session, with 849 passing the four filters. Phase counts sum to the unique row count, all strict threshold checks pass, and every row has its chart file.

Chromium checks passed at 1440 × 900 and 390 × 844. Full Reversal Extension column copy contained the exact 16 expected symbols; searching COCHINSHIP copied only `NSE:COCHINSHIP`; an impossible search disabled every column copy button. Combining bullish direction, fresh signals and RS ≥80 produced three table rows. All sort options, phase focus/reset, board/table round trip, CSV download, single-symbol copy, and chart ranges were exercised.

Both uploaded reference images loaded. Scan rules displayed all ten labels. Chart hover displayed OHLC and volume. Dark/light round trip passed; phase-text light-mode contrast was strengthened. Dense 602-stock Trend / Holding lane scrolls without shrinking or clipping card content. Mobile page and detail-dialog widths do not overflow their containers.

Injected snapshot and chart failures displayed honest error messages. No JavaScript page errors were observed. Charts and dialogs were visually inspected on desktop and mobile.

The first GitHub scanner run and the final full refresh both completed successfully. The final [verified Actions run](https://github.com/arjunbchavan1989-AB/nse-kell-price-cycle/actions/runs/38510212182) passed all 12 tests, restored 839 fresh histories, fetched the remaining ten, and produced 849 eligible stocks with 100% same-session coverage. GitHub Pages reports `built`. A live Chromium visit confirmed the polished cards are 74px high with 74px content height and `flex-shrink: 0`, and the live build timestamp matches the final refresh.
