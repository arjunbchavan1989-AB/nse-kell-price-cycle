import sys,unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"pipeline"))
import market_data as market


def frame(volume=600000,day="2026-10-14"):
    return pd.DataFrame({"Open":100.,"High":103.,"Low":97.,"Close":100.,
                         "Adj Close":100.,"Volume":volume},
                        index=pd.bdate_range(end=day,periods=100))


class IndependentMarketTests(unittest.TestCase):
    def test_universe_volume_threshold_is_strict(self):
        thin=frame(70000)
        for column in ("Open","High","Low","Close","Adj Close"):thin[column]*=10
        _,ok=market.liquidity(thin)
        self.assertFalse(ok)
        _,ok=market.liquidity(frame(600000))
        self.assertTrue(ok)

    def test_universe_rupee_threshold_is_strict(self):
        _,ok=market.liquidity(frame(300000))
        self.assertFalse(ok)

    def test_range_threshold_is_strict(self):
        f=frame();f["High"]=101.5;f["Low"]=98.5
        values,ok=market.liquidity(f)
        self.assertEqual(values["avg_range_pct_20d"],3)
        self.assertFalse(ok)

    def test_completed_session_before_and_after_close_guard(self):
        before=datetime(2026,10,14,18,tzinfo=ZoneInfo("Asia/Kolkata"))
        after=before.replace(hour=19)
        self.assertEqual(str(market.completed_date(before)),"2026-10-13")
        self.assertEqual(str(market.completed_date(after)),"2026-10-14")

    def test_future_bars_are_not_cached_as_completed(self):
        self.assertEqual(str(market.clean(frame(day="2026-10-15"),pd.Timestamp("2026-10-14")).index[-1].date()),"2026-10-14")

    def test_own_shares_and_strict_market_cap_without_other_feed(self):
        members=pd.DataFrame({"SYMBOL":["A","B"],"NAME OF COMPANY":["Company A","Company B"]})
        with patch.object(market,"listing",return_value=(members,"Own listing")), \
             patch.object(market,"exchange_session",return_value=pd.Timestamp("2026-10-14")), \
             patch.object(market,"histories",return_value=({"A":frame(),"B":frame()},[])), \
             patch.object(market,"shares",return_value=({"A":50000000,"B":50100000},[])):
            source,frames=market.build()
        self.assertEqual([r["symbol"] for r in source["rows"]],["B"])
        self.assertAlmostEqual(source["rows"][0]["market_cap_cr"],501)
        self.assertEqual(source["market_data"]["mode"],"Independent per-repository acquisition")
        self.assertEqual(set(frames),{"B"})

    def test_mixed_own_sessions_fail(self):
        members=pd.DataFrame({"SYMBOL":["A","B"],"NAME OF COMPANY":["A","B"]})
        with patch.object(market,"listing",return_value=(members,"Own listing")), \
             patch.object(market,"exchange_session",return_value=pd.Timestamp("2026-10-14")), \
             patch.object(market,"histories",return_value=({"A":frame(),"B":frame(day="2026-10-13")},[])):
            with self.assertRaises(RuntimeError):market.build()

    def test_no_other_repository_feed_in_runtime(self):
        root=Path(__file__).resolve().parents[1]
        for relative in ("pipeline/market_data.py","pipeline/run.py",".github/workflows/daily-update.yml"):
            text=(root/relative).read_text()
            self.assertNotIn("nse-stage-analysis",text)
            self.assertNotIn("repository: arjunbchavan1989-AB/nse-kell-price-cycle",text)
