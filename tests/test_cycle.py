import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"pipeline"))
from cycle import classify, indicators, PHASES
from benchmark import excess


def bars(close):
    close=np.asarray(close,dtype=float)
    return pd.DataFrame({"open":close,"high":close+1,"low":close-1,
                         "close":close,"volume":100000.},
                        index=pd.bdate_range("2025-01-01",periods=len(close)))


class CycleTests(unittest.TestCase):
    def test_wilder_seed(self):
        d=indicators(bars(np.full(120,100.)))
        self.assertEqual(d.atr.iloc[13],2.)
        self.assertEqual(d.atr.iloc[-1],2.)

    def test_breakout_references_exclude_current_bar(self):
        f=bars(np.full(120,100.));f.iloc[-1,f.columns.get_loc("high")]=1000
        f.iloc[-1,f.columns.get_loc("volume")]=900000
        d=indicators(f)
        self.assertEqual(d.pivot5_hi.iloc[-1],101.)
        self.assertEqual(d.volume_ratio.iloc[-1],9.)

    def test_flat_is_not_forced_into_a_setup(self):
        result,_=classify(bars(np.full(120,100.)))
        self.assertEqual(result["phase"],"NC")
        self.assertIsNone(result["signal"])

    def test_downside_extension(self):
        result,_=classify(bars([100.]*119+[80.]))
        self.assertEqual(result["signal"],"RE")

    def test_upside_extension(self):
        result,_=classify(bars([100.]*119+[120.]))
        self.assertEqual(result["signal"],"EE")

    def test_warmup(self):
        result,_=classify(bars([100.]*30+[80.]))
        self.assertEqual(result["phase"],"NC")

    def test_no_lookahead(self):
        f=bars(100+np.sin(np.arange(160)/5)*8+np.arange(160)*.03)
        prefix=indicators(f.iloc[:120]);full=indicators(f)
        pd.testing.assert_frame_equal(prefix,full.iloc[:120])
        a,_=classify(f.iloc[:120]);b,_=classify(f.iloc[:120].copy())
        self.assertEqual(a,b)

    def test_rs_uses_common_sessions(self):
        f=bars(np.arange(100,200))
        b=pd.DataFrame({"close":np.arange(100,200)*2},index=f.index)
        self.assertAlmostEqual(excess(f,b),0.)
        self.assertIsNone(excess(f.iloc[:50],b))

    def test_all_labels_unique(self):
        self.assertEqual(len(PHASES),len(set(p[0] for p in PHASES)))

    def test_first_crossback_is_not_repeated(self):
        # Isolate the sequential state machine from indicator arithmetic.
        f=bars([100.]*104)
        d=indicators(f)
        d["ema10"]=99.; d["ema20"]=98.; d["ema20_slope"]=1.
        d["extension10"]=.5; d["extension20"]=1.
        d["prior_below"]=0.; d["prior_above"]=0.
        d["volume_ratio"]=1.; d["pivot5_hi"]=200.; d["pivot5_lo"]=50.
        d["base_width_atr"]=10.; d["contraction"]=1.; d["position"]=.8
        d.iloc[98,d.columns.get_loc("close")]=97.
        d.iloc[99,d.columns.get_loc("prior_below")]=5.
        d.iloc[99,d.columns.get_loc("pivot5_hi")]=99.
        d.iloc[99,d.columns.get_loc("volume_ratio")]=1.3
        d.iloc[100,d.columns.get_loc("close")]=101.
        d.iloc[101,d.columns.get_loc("close")]=102.
        result,_=None,None
        with patch("cycle.indicators",return_value=d):
            result,_=classify(f)
        self.assertEqual([e["code"] for e in result["events"]],["WP","CB"])


if __name__=="__main__":
    unittest.main()
