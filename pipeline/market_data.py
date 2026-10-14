"""Independent NSE listing, EOD histories and shares. Never reads another dashboard."""
import json,logging,math,time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from io import BytesIO
from pathlib import Path
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import yfinance as yf

HERE=Path(__file__).resolve().parent
CACHE=HERE/"cache";CACHE.mkdir(exist_ok=True)
LOG=logging.getLogger("market")
LISTING_URL="https://archives.nseindia.com/content/equities/EQUITY_L.csv"
FILTERS={"min_market_cap_cr":500,"min_avg_volume_shares":70000,"min_avg_rupee_vol_cr":3,
         "min_avg_daily_range_pct":3,"avg_volume_window_days":20}

def completed_date(now=None):
    now=now or datetime.now(ZoneInfo("Asia/Kolkata"))
    return now.date() if now.hour>=19 else now.date()-timedelta(days=1)

def exchange_session(completed):
    for offset in range(5):
        day=completed-timedelta(days=offset)
        url=f"https://archives.nseindia.com/content/indices/ind_close_all_{day:%d%m%Y}.csv"
        try:
            with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=20) as r:
                frame=pd.read_csv(BytesIO(r.read()))
            frame.columns=frame.columns.str.strip()
            row=frame[frame["Index Name"].str.strip().str.casefold()=="nifty midsmallcap 400"]
            if len(row)==1 and float(row.iloc[0]["Closing Index Value"])>0 and pd.to_datetime(row.iloc[0]["Index Date"],dayfirst=True).date()==day:
                return pd.Timestamp(day)
        except Exception as exc:LOG.debug("Index session unavailable for %s: %s",day,exc)
    raise RuntimeError("Cannot verify a recent completed NSE EOD session")

def listing():
    path=CACHE/"equity_l.csv";status="Fresh official NSE listing"
    try:
        with urlopen(Request(LISTING_URL,headers={"User-Agent":"Mozilla/5.0"}),timeout=30) as r:raw=r.read()
        frame=pd.read_csv(BytesIO(raw))
        if len(frame)<1000 or "SYMBOL" not in frame:raise RuntimeError("Malformed NSE listing")
        path.write_bytes(raw)
    except Exception:
        if not path.exists() or time.time()-path.stat().st_mtime>7*86400:raise RuntimeError("Official listing unavailable and no recent own cache")
        frame=pd.read_csv(path);status="Own official-listing cache (at most seven days old)"
    frame.columns=frame.columns.str.strip()
    frame=frame[frame["SERIES"].str.strip()=="EQ"].copy()
    frame["SYMBOL"]=frame["SYMBOL"].str.strip()
    frame["NAME OF COMPANY"]=frame["NAME OF COMPANY"].str.strip()
    return frame.drop_duplicates("SYMBOL"),status

def clean(frame,session):
    frame=frame.copy().dropna(subset=["Open","High","Low","Close","Volume"])
    frame.index=pd.to_datetime(frame.index).tz_localize(None).normalize()
    frame=frame[~frame.index.duplicated(keep="last")].sort_index()
    return frame.loc[(frame.index<=session)&(frame.Volume>0)]

def histories(symbols,session):
    path=CACHE/"eod_history.pkl";cache=pd.read_pickle(path) if path.exists() else {}
    fresh={};missing=[]
    for symbol in symbols:
        old=clean(cache[symbol],session) if symbol in cache else None
        if old is not None and len(old)>=21 and old.index[-1]==session:fresh[symbol]=old
        else:missing.append(symbol)
    LOG.info("Own EOD histories cached: %s; downloading %s listed stocks",len(fresh),len(missing))
    for attempt in range(2):
        failed=[]
        for offset in range(0,len(missing),80):
            batch=missing[offset:offset+80]
            try:
                data=yf.download([s+".NS" for s in batch],period="15mo",interval="1d",auto_adjust=False,
                                 group_by="ticker",threads=4,progress=False,timeout=20)
            except Exception as exc:
                LOG.warning("Quote batch unavailable: %s",exc);failed.extend(batch);continue
            for symbol in batch:
                try:
                    frame=clean(data[symbol+".NS"] if isinstance(data.columns,pd.MultiIndex) else data,session)
                    if len(frame)>=21:
                        cache[symbol]=frame;fresh[symbol]=frame
                        if frame.index[-1]!=session:failed.append(symbol)
                    else:failed.append(symbol)
                except (KeyError,ValueError,TypeError):failed.append(symbol)
            pd.to_pickle(cache,path)
            LOG.info("Own quote progress: %s/%s listed stocks",len(fresh),len(symbols))
            time.sleep(.25)
        missing=failed
        if not missing:break
        if attempt==0:time.sleep(10)
    return fresh,sorted(set(symbols)-set(fresh))

def liquidity(frame):
    raw=frame.rename(columns=str.lower);previous=raw.close.shift(1)
    tr=pd.concat([raw.high-raw.low,(raw.high-previous).abs(),(raw.low-previous).abs()],axis=1).max(axis=1)
    values={"close":float(raw.close.iloc[-1]),"avg_vol_20d":float(raw.volume.tail(20).mean()),
            "avg_rvol_20d_cr":float((raw.close*raw.volume).tail(20).mean()/1e7),
            "avg_range_pct_20d":float((tr/previous*100).tail(20).mean())}
    passes=(all(math.isfinite(v) for v in values.values()) and values["close"]>0
            and values["avg_vol_20d"]>70000 and values["avg_rvol_20d_cr"]>3 and values["avg_range_pct_20d"]>3)
    return values,passes

def shares(symbols):
    today=datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat();path=CACHE/"shares.json"
    cache=json.loads(path.read_text()) if path.exists() else {};values={}
    for symbol in symbols:
        entry=cache.get(symbol,{})
        if entry.get("date")==today and entry.get("shares",0)>0:values[symbol]=entry["shares"]
    def fetch(symbol):
        try:
            value=float(yf.Ticker(symbol+".NS").fast_info["shares"])
            if np.isfinite(value) and value>0:return symbol,value
        except Exception:pass
        return symbol,None
    for attempt in range(2):
        missing=[s for s in symbols if s not in values]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for symbol,value in pool.map(fetch,missing):
                if value is not None:values[symbol]=value;cache[symbol]={"date":today,"shares":value}
        path.write_text(json.dumps(cache,allow_nan=False))
        LOG.info("Own shares coverage: %s/%s liquidity-qualified stocks",len(values),len(symbols))
        if len(values)==len(symbols):break
        if attempt==0:time.sleep(10)
    if not symbols or len(values)/len(symbols)<.95:raise RuntimeError("Own shares coverage below 95%; refusing incomplete market-cap universe")
    return values,sorted(set(symbols)-set(values))

def build():
    members,listing_status=listing();symbols=members.SYMBOL.tolist()
    session=exchange_session(completed_date());frames,missing_prices=histories(symbols,session)
    if not frames or len(frames)/len(symbols)<.65:raise RuntimeError("Provider histories cover under 65% of official listings; refusing publication")
    current={s:f for s,f in frames.items() if f.index[-1]==session}
    if len(current)/len(frames)<.95:raise RuntimeError("Own same-session history coverage below 95%")
    metrics={s:liquidity(f) for s,f in current.items()};liquid=[s for s,(_,ok) in metrics.items() if ok]
    counts,missing_shares=shares(liquid);rows=[];eligible={}
    for symbol in liquid:
        if symbol not in counts:continue
        values=metrics[symbol][0];cap=values["close"]*counts[symbol]/1e7
        if cap<=500:continue
        rows.append({"symbol":symbol,"market_cap_cr":cap,**values});eligible[symbol]=current[symbol]
    if not rows:raise RuntimeError("No independently eligible stocks; retaining last good output")
    now=datetime.now(ZoneInfo("Asia/Kolkata"));batch=now.astimezone(timezone.utc).replace(hour=14,minute=0,second=0,microsecond=0)
    if now<batch:batch-=timedelta(days=1)
    health={"mode":"Independent per-repository acquisition","listing_url":LISTING_URL,"listing_status":listing_status,
            "official_listing_count":len(symbols),"retrieved_count":len(frames),
            "listing_history_coverage_pct":round(len(frames)/len(symbols)*100,2),
            "same_session_count":len(current),"same_session_coverage_pct":round(len(current)/len(frames)*100,2),
            "liquidity_passed":len(liquid),"qualified_count":len(rows),"shares_coverage_pct":round(len(counts)/len(liquid)*100,2),
            "missing_price_symbols":missing_prices,"stale_price_symbols":sorted(set(frames)-set(current)),
            "missing_shares_symbols":missing_shares,"equity_prices":"Yahoo Finance via yfinance",
            "market_cap":"Own daily Yahoo shares outstanding × own raw EOD close","session_validation":"Dated NSE index-close archive"}
    payload={"generated_at":now.isoformat(),"refresh_batch":batch.isoformat(),"last_trading_date":str(session.date()),
             "filters":FILTERS,"coverage_pct":100.0,"rows":rows,"market_data":health,
             "company_names":dict(zip(members.SYMBOL,members["NAME OF COMPANY"]))}
    LOG.info("Independent universe: %s eligible; EOD %s; listing history coverage %.2f%%",
             len(rows),session.date(),health["listing_history_coverage_pct"])
    return payload,eligible
