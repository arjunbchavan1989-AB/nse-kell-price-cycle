"""Wait for this evening's public upstream snapshot, without cross-repo secrets.

Read main, not a potentially cached Pages response. Only the disposable upstream
checkout is reset. The downstream scan does not start against yesterday's file.
"""
import argparse
import json
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


def batch_cutoff(now):
    target = now.astimezone(timezone.utc).replace(hour=14, minute=0, second=0, microsecond=0)
    return target if now >= target else target - timedelta(days=1)


def fresh(data, cutoff, now):
    try:
        generated = datetime.fromisoformat(data["generated_at"])
        batch = datetime.fromisoformat(data["refresh_batch"])
        return (generated.tzinfo is not None and batch.tzinfo is not None
                and cutoff <= generated <= now + timedelta(minutes=5)
                and batch == cutoff and bool(data["rows"]) and bool(data["last_trading_date"]))
    except (KeyError, TypeError, ValueError):
        return False


def wait(checkout, timeout_minutes=120, interval=60):
    checkout = Path(checkout).resolve()
    if not (checkout / ".git").exists():
        raise RuntimeError("Expected an isolated upstream Git checkout")
    started = time.monotonic()
    now = datetime.now(timezone.utc)
    cutoff = batch_cutoff(now)
    print(f"Waiting for upstream batch {cutoff.isoformat()}", flush=True)
    while True:
        try:
            subprocess.run(["git", "fetch", "origin", "main", "--depth=1"],
                           cwd=checkout, check=True, timeout=90)
            subprocess.run(["git", "reset", "--hard", "FETCH_HEAD"],
                           cwd=checkout, check=True, timeout=30)
            payload = json.loads((checkout / "web/data/latest.json").read_text())
            if fresh(payload, cutoff, datetime.now(timezone.utc)):
                print(f"Fresh upstream: EOD {payload['last_trading_date']}; "
                      f"generated {payload['generated_at']}", flush=True)
                return
            print("Upstream has not published this batch yet; retaining downstream snapshot.",
                  flush=True)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            print(f"Upstream not ready: {exc}", flush=True)
        if time.monotonic() - started >= timeout_minutes * 60:
            raise RuntimeError("Fresh upstream wait timed out; refusing stale publication")
        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--timeout-minutes", type=int, default=120)
    args = parser.parse_args()
    wait(args.checkout, args.timeout_minutes)
