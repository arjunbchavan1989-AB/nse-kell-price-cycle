import sys,unittest,re,os
from unittest.mock import patch
from datetime import date,datetime
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"pipeline"))
from refresh_guard import decision,run
from argparse import Namespace

class FreshnessTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,15,19,45,tzinfo=ZoneInfo("Asia/Kolkata"))
        self.today=date(2026,10,15)
        self.p={"last_trading_date":"2026-10-15","generated_at":"2026-10-15T19:38:00+05:30",
                "market_data":{"mode":"Independent per-repository acquisition"}}
    def test_current_session_skips(self):
        self.assertFalse(decision(self.p,self.today,self.now)[0])
    def test_stale_session_refreshes(self):
        self.p["last_trading_date"]="2026-10-14"
        self.assertTrue(decision(self.p,self.today,self.now)[0])
    def test_weekday_missing_report_retries(self):
        self.p["last_trading_date"]="2026-10-14"
        self.assertTrue(decision(self.p,date(2026,10,14),self.now)[0])
    def test_weekend_uses_latest_verified_session(self):
        self.p["last_trading_date"]="2026-10-16";self.p["generated_at"]="2026-10-16T19:38:00+05:30"
        self.assertFalse(decision(self.p,date(2026,10,16),datetime(2026,10,17,19,45,tzinfo=self.now.tzinfo))[0])
    def test_ui_only_build_time_does_not_mask_stale_prices(self):
        self.p["last_trading_date"]="2026-10-14";self.p["generated_at"]="2026-10-15T19:40:00+05:30"
        self.assertTrue(decision(self.p,self.today,self.now)[0])
    def test_bootstrap_never_fresh(self):
        self.p["mode"]="Dated bootstrap preview"
        self.assertTrue(decision(self.p,self.today,self.now)[0])
    def test_dependent_feed_never_fresh(self):
        self.p["market_data"]["mode"]="Other dashboard feed"
        self.assertTrue(decision(self.p,self.today,self.now)[0])
    def test_invalid_timestamp_refreshes(self):
        self.p["generated_at"]="bad"
        self.assertTrue(decision(self.p,self.today,self.now)[0])
    def test_missing_snapshot_refreshes(self):
        self.assertTrue(decision(None,self.today,self.now)[0])
    def test_future_timestamp_refreshes(self):
        self.p["generated_at"]="2026-10-15T20:00:00+05:30"
        self.assertTrue(decision(self.p,self.today,self.now)[0])
    def test_manual_force_and_ui_only(self):
        a=Namespace(event="workflow_dispatch",refresh_data="true",push_refresh=False)
        with patch.dict(os.environ,{},clear=True):
            self.assertTrue(run(a)["refresh"])
            a.refresh_data="false";self.assertFalse(run(a)["refresh"])
    def test_approved_cron_slots(self):
        source=(Path(__file__).resolve().parents[1]/".github/workflows/daily-update.yml").read_text()
        self.assertEqual(re.findall(r"cron:\s*'([^']+)'",source),["0 14 * * *","15 14 * * *","30 14 * * *"])
    def test_freshness_output_is_wired_into_acquisition(self):
        source=(Path(__file__).resolve().parents[1]/".github/workflows/daily-update.yml").read_text()
        self.assertIn("id: freshness",source)
        self.assertIn("if: steps.freshness.outputs.refresh == 'true'",source)
        self.assertIn("python pipeline/refresh_guard.py --snapshot",source)
