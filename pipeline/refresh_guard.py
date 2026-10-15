"""Independent, conservative EOD freshness gate for scheduled retries."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

IST=ZoneInfo("Asia/Kolkata")

def decision(snapshot,verified_session,now):
    """Return (refresh,reason). A missing weekday report is not proof of holiday."""
    from datetime import timedelta
    now=now.astimezone(IST)
    cutoff=now.date() if now.hour>=19 else now.date()-timedelta(days=1)
    verified=verified_session.date() if isinstance(verified_session,datetime) else verified_session
    if verified>cutoff:return True,"Exchange verification returned a future session"
    if cutoff.weekday()<5 and verified<cutoff:
        return True,"Weekday exchange archive lags today's cutoff; retry rather than assume a holiday"
    if not isinstance(snapshot,dict):return True,"No valid own snapshot"
    if snapshot.get("last_trading_date")!=verified.isoformat():
        return True,"Snapshot is behind the latest verified completed NSE session"
    health=snapshot.get("market_data") or {}
    if health.get("bootstrap") or "bootstrap" in str(snapshot.get("mode","")).lower():
        return True,"Bootstrap snapshots cannot satisfy freshness"
    if not str(health.get("mode","")).startswith("Independent"):
        return True,"Snapshot does not establish independent acquisition"
    try:
        generated=datetime.fromisoformat(snapshot["generated_at"])
        if generated.tzinfo is None:return True,"Snapshot generation time lacks timezone"
        if generated>now:return True,"Snapshot generation time is in the future"
        if generated.astimezone(IST).date()<verified:return True,"Snapshot predates its claimed EOD session"
    except (KeyError,ValueError,TypeError):
        return True,"Snapshot generation time is invalid"
    return False,"Own independent snapshot already covers the latest verified completed NSE session"

def run(args):
    if args.event=="workflow_dispatch":
        refresh=args.refresh_data.lower()=="true"
        reason="Manual forced refresh" if refresh else "Manual UI-only deployment"
    elif args.event=="push":
        refresh=args.push_refresh
        reason="Code-push refresh policy" if refresh else "Code-push UI-only deployment"
    else:
        try:
            from market_data import completed_date,exchange_session
            expected=exchange_session(completed_date()).date()
            p=Path(args.snapshot)
            snapshot=json.loads(p.read_text()) if p.exists() else None
            refresh,reason=decision(snapshot,expected,datetime.now(IST))
        except Exception as exc:
            refresh=True
            reason=f"Cannot establish freshness ({type(exc).__name__}); defer to the validated scanner"
    record={"refresh":refresh,"reason":reason,"checked_at":datetime.now(IST).isoformat()}
    print(json.dumps(record))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a") as f:f.write(f"refresh={str(refresh).lower()}\n")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a") as f:
            f.write(f"### EOD freshness check\n- Acquire data: **{refresh}**\n- {reason}\n")
    return record

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--snapshot",required=True)
    parser.add_argument("--event",choices=["schedule","workflow_dispatch","push"],required=True)
    parser.add_argument("--refresh-data",default="")
    parser.add_argument("--push-refresh",action="store_true")
    run(parser.parse_args())
