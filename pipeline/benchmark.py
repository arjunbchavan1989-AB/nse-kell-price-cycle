"""NSE MidSmallcap 400 benchmark. Independent of the paused equity-source migration."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
import pandas as pd

NAME = "Nifty MidSmallcap 400"
PATH = Path(__file__).parent / "benchmark_midsmall400.csv"


def load(as_of):
    end = pd.Timestamp(as_of).normalize()
    data = pd.read_csv(PATH, parse_dates=["date"]).set_index("date") if PATH.exists() else pd.DataFrame(columns=["close"])
    missing = [day for day in pd.bdate_range(end-pd.Timedelta(days=140),end) if day not in data.index]
    def fetch(day):
        try:
            url = f"https://archives.nseindia.com/content/indices/ind_close_all_{day:%d%m%Y}.csv"
            with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=15) as r:
                f = pd.read_csv(BytesIO(r.read()))
            f.columns = f.columns.str.strip()
            row = f[f["Index Name"].str.strip().str.casefold()==NAME.casefold()]
            if len(row)!=1: return None
            row=row.iloc[0]
            actual=pd.to_datetime(row["Index Date"],dayfirst=True).normalize()
            value=float(row["Closing Index Value"])
            return {"date":actual,"close":value} if actual==day and value>0 else None
        except Exception:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        new=[r for r in pool.map(fetch,missing) if r is not None]
    if new: data=pd.concat([data,pd.DataFrame(new).set_index("date")])
    data=data[~data.index.duplicated(keep="last")].sort_index().loc[:end]
    if len(data)<64 or data.index[-1]!=end:
        raise RuntimeError("MidSmallcap 400 benchmark is incomplete or stale")
    data.rename_axis("date").to_csv(PATH)
    return data


def excess(stock, benchmark):
    aligned=pd.concat([stock.close.rename("s"),benchmark.close.rename("b")],axis=1,join="inner").dropna()
    if len(aligned)<64: return None
    return float((aligned.s.iloc[-1]/aligned.s.iloc[-64]-1)-(aligned.b.iloc[-1]/aligned.b.iloc[-64]-1))*100
