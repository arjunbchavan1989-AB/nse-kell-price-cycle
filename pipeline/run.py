"""Daily scanner for a shared Indian-equity universe.

Uses the existing stage dashboard's candidate universe and shares-based market
capitalization; rechecks its four liquidity/size filters at this scan's close.
Equity OHLCV stays on Yahoo: the user paused the separate NSE migration.
"""
import argparse
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import yfinance as yf
from benchmark import load as load_benchmark, excess, NAME as BENCHMARK
from cycle import classify, CONFIG, PHASES

HERE=Path(__file__).parent
ROOT=HERE.parent
CACHE=HERE/"cache"
CACHE.mkdir(exist_ok=True)
WEB=ROOT/"web"
FEED="https://arjunbchavan1989-ab.github.io/nse-stage-analysis/data/latest.json"
FILTERS={"min_market_cap_cr":500, "min_avg_volume_shares":70000, "min_avg_rupee_vol_cr":3,
         "min_avg_daily_range_pct":3, "avg_volume_window_days":20}
LOG=logging.getLogger("kell")


def completed_date():
    now=datetime.now(ZoneInfo("Asia/Kolkata"))
    return now.date() if now.hour>=19 else now.date()-timedelta(days=1)


def get_universe(source_file=None):
    if source_file:
        data=json.loads(Path(source_file).read_text())
    else:
        with urlopen(Request(FEED,headers={"User-Agent":"NSE-Kell-Dashboard/1.0"}),timeout=30) as r:
            data=json.load(r)
    if not data.get("rows") or not data.get("last_trading_date"):
        raise RuntimeError("Shared universe feed is empty or malformed")
    for k,v in FILTERS.items():
        if data.get("filters",{}).get(k)!=v:
            raise RuntimeError(f"Shared universe changed its {k} filter")
    asof=pd.Timestamp(data["last_trading_date"]).date()
    if (completed_date()-asof).days>7:
        raise RuntimeError("Shared universe is more than 7 calendar days old; retaining last good output")
    return data


def download(symbols,end,seed_cache=None):
    path=CACHE/"history.pkl"
    cache=pd.read_pickle(path) if path.exists() else {}
    if seed_cache:
        seed=pd.read_pickle(seed_cache)
        for symbol in symbols:
            key=symbol+".NS"
            if key in seed.columns.get_level_values(0):
                frame=seed[key].dropna(subset=["Open","High","Low","Close","Volume"])
                if len(frame): cache[symbol]=frame
    fresh={}
    missing=[]
    for symbol in symbols:
        frame=cache.get(symbol)
        if frame is not None:
            frame=frame.loc[frame.index<=end]
        if frame is not None and len(frame)>=100 and frame.index[-1].date()==end.date():
            fresh[symbol]=frame
        else:
            missing.append(symbol)
    LOG.info("Fresh cached histories: %s; fetching %s",len(fresh),len(missing))
    for attempt in range(3):
        if not missing: break
        failed=[]
        for offset in range(0,len(missing),40):
            batch=missing[offset:offset+40]
            tickers=[s+".NS" for s in batch]
            data=yf.download(tickers,period="15mo",interval="1d",auto_adjust=False,
                             group_by="ticker",threads=4,progress=False,timeout=20)
            for symbol in batch:
                try:
                    frame=data[symbol+".NS"] if isinstance(data.columns,pd.MultiIndex) else data
                    frame=frame.dropna(subset=["Open","High","Low","Close","Volume"]).copy()
                    frame.index=pd.to_datetime(frame.index).tz_localize(None).normalize()
                    frame=frame.loc[frame.index<=end]
                    if len(frame)>=20 and (end.date()-frame.index[-1].date()).days<=4:
                        fresh[symbol]=frame
                        cache[symbol]=frame
                    else: failed.append(symbol)
                except (KeyError,ValueError):
                    failed.append(symbol)
            pd.to_pickle(cache,path)
            time.sleep(.5)
        missing=failed
        LOG.info("Attempt %s: %s/%s histories retrieved",attempt+1,len(fresh),len(symbols))
        if missing and attempt<2: time.sleep(5*(attempt+1))
    pd.to_pickle(cache,path)
    return fresh,missing


def safe(value,digits=2):
    return round(float(value),digits) if value is not None and np.isfinite(value) else None


def scan(source_file=None,seed_cache=None):
    source=get_universe(source_file)
    mapping={r["symbol"]:r for r in source["rows"]}
    # Anchor every price/filter/benchmark calculation to the shared universe EOD.
    # Never combine a newer stock close with an older candidate-universe session.
    end=pd.Timestamp(source["last_trading_date"])
    if end.date()>completed_date():
        raise RuntimeError("Shared universe refers to an incomplete/future session")
    histories,missing=download(list(mapping),end,seed_cache)
    if not histories or len(histories)/len(mapping)<.95:
        raise RuntimeError(f"History coverage below 95% ({len(histories)}/{len(mapping)}); retaining last good snapshot")
    # Exclude stale daily histories rather than mixing sessions in breadth stats.
    session=max(f.index[-1] for f in histories.values())
    if session != end:
        raise RuntimeError("Price session does not match the shared universe EOD; retaining last good output")
    current={s:f for s,f in histories.items() if f.index[-1]==session}
    if len(current)/len(mapping)<.95:
        raise RuntimeError(f"Same-session coverage below 95% ({len(current)}/{len(mapping)})")
    if (end-session).days>4:
        raise RuntimeError("Price data is stale by more than 4 calendar days")
    benchmark=load_benchmark(str(session.date()))
    rows=[]
    charts={}
    for symbol,frame in current.items():
        raw=frame.rename(columns=str.lower)
        previous=raw.close.shift(1)
        tr=pd.concat([raw.high-raw.low,(raw.high-previous).abs(),(raw.low-previous).abs()],axis=1).max(axis=1)
        avg_vol=raw.volume.tail(20).mean()
        avg_rvol=(raw.close*raw.volume).tail(20).mean()/1e7
        # Keep compatibility with the original dashboard's implemented range filter.
        range_pct=(tr/previous*100).tail(20).mean()
        parent=mapping[symbol]
        implied_shares=parent["market_cap_cr"]*1e7/parent["close"]
        mcap=implied_shares*raw.close.iloc[-1]/1e7
        if not (mcap>500 and avg_vol>70000 and avg_rvol>3 and range_pct>3): continue
        # Dividend-adjusted technical prices; latest raw close remains displayed.
        technical=raw.copy()
        if "adj close" in raw:
            ratio=raw["adj close"]/raw.close
            for column in ("open","high","low","close"): technical[column]*=ratio
        result,d=classify(technical)
        last=d.iloc[-1]
        stock_excess=excess(technical,benchmark)
        chg=(raw.close.iloc[-1]/raw.close.iloc[-2]-1)*100
        row={
            "symbol":symbol,"phase":result["phase"],"previous_phase":result["previous_phase"],
            "changed":result["changed"],"regime":result["regime"],"signal_today":result["signal"],
            "signal_age":result["signal_age"],"last_event":result["last_event"],
            "reasons":result["reasons"],"retest_highs":result["retest_highs"],
            "close":safe(raw.close.iloc[-1]),"change_pct":safe(chg),"rs_excess_pct":safe(stock_excess),
            "market_cap_cr":safe(mcap,1),"avg_vol_20d":int(avg_vol),
            "avg_rvol_20d_cr":safe(avg_rvol),"avg_range_pct_20d":safe(range_pct,4),
            "vol_ratio":safe(last.volume_ratio),"ema10":safe(last.ema10),"ema20":safe(last.ema20),
            "atr":safe(last.atr),"extension10_atr":safe(last.extension10),
            "extension20_atr":safe(last.extension20),"base_width_atr":safe(last.base_width_atr),
            "contraction_ratio":safe(last.contraction),"date":str(session.date()),
        }
        rows.append(row)
        bars=[]
        for dt,r in d.tail(180).iterrows():
            bars.append({"t":str(dt.date()),"o":safe(r.open),"h":safe(r.high),"l":safe(r.low),
                         "c":safe(r.close),"v":int(r.volume),"e10":safe(r.ema10),"e20":safe(r.ema20)})
        charts[symbol]={"symbol":symbol,"date":str(session.date()),"bars":bars,
                        "events":result["events"],"price_basis":"Dividend-adjusted OHLCV technical chart"}
    if not rows: raise RuntimeError("No eligible rows; refusing an empty publication")
    values=np.array([r["rs_excess_pct"] for r in rows if r["rs_excess_pct"] is not None])
    for r in rows:
        r["rs_pct"]=int((values<r["rs_excess_pct"]).sum()/len(values)*100) if r["rs_excess_pct"] is not None and len(values) else None
    counts={code:sum(r["phase"]==code for r in rows) for code,*_ in PHASES}
    phases=[{"code":c,"name":n,"color":color,"family":family} for c,n,color,family in PHASES]
    payload={
        "generated_at":datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(),
        "last_trading_date":str(session.date()),"universe_date":source["last_trading_date"],
        "universe_source":FEED,"candidate_count":len(mapping),"retrieved_count":len(histories),
        "current_session_count":len(current),"qualified_count":len(rows),
        "coverage_pct":safe(len(current)/len(mapping)*100),
        "missing_symbols":sorted(set(mapping)-set(current)),"benchmark":BENCHMARK,
        "filters":FILTERS,"range_definition":"20-session mean of daily True Range / previous close × 100 (compatible with the existing dashboard)",
        "classification":"Rule-based approximation of the supplied Oliver Kell diagrams; not official/proprietary Kell formulas",
        "data_sources":{"equity_prices":"Yahoo Finance via yfinance","benchmark":"NSE index-close archives",
                        "market_cap":"Shared-universe market cap, re-marked to the scan close using implied shares",
                        "universe":"Existing NSE stage-analysis dashboard candidate feed"},
        "config":CONFIG,"phases":phases,"counts":counts,
        "new_signals":sum(r["signal_today"] is not None for r in rows),
        "transitions":sum(r["changed"] for r in rows),"rows":sorted(rows,key=lambda r:r["symbol"]),
    }
    # Prepare all files first. Output is written only after coverage/data checks.
    chart_dir=WEB/"data/charts"
    chart_dir.mkdir(parents=True,exist_ok=True)
    for symbol,chart in charts.items():
        (chart_dir/f"{symbol}.json").write_text(json.dumps(chart,separators=(",",":"),allow_nan=False))
    text=json.dumps(payload,separators=(",",":"),allow_nan=False)
    (WEB/"data/latest.json").write_text(text)
    archive=ROOT/"snapshots"; archive.mkdir(exist_ok=True)
    (archive/f"{session.date()}.json").write_text(text)
    LOG.info("Scan complete: %s eligible stocks, %s%% coverage, %s fresh signals",len(rows),payload["coverage_pct"],payload["new_signals"])
    return payload


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source-file")
    p.add_argument("--seed-cache")
    a=p.parse_args()
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(message)s")
    scan(a.source_file,a.seed_cache)
