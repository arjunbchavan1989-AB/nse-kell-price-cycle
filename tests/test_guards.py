import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"pipeline"))
import run
from test_cycle import bars


class PublicationGuards(unittest.TestCase):
    def check_failure_preserves_snapshot(self,source,histories,message):
        with tempfile.TemporaryDirectory() as temp:
            web=Path(temp)/"web"
            (web/"data").mkdir(parents=True)
            target=web/"data/latest.json"
            target.write_text(json.dumps({"sentinel":"last-good"}))
            with patch.object(run,"WEB",web),patch.object(run,"get_universe",return_value=source),\
                 patch.object(run,"completed_date",return_value=pd.Timestamp(source["last_trading_date"]).date()),\
                 patch.object(run,"download",return_value=(histories,[])):
                with self.assertRaisesRegex(RuntimeError,message):
                    run.scan()
            self.assertEqual(json.loads(target.read_text()),{"sentinel":"last-good"})

    def test_low_coverage_cannot_overwrite_snapshot(self):
        f=bars([100.]*120)
        source={"last_trading_date":str(f.index[-1].date()),
                "rows":[{"symbol":str(i)} for i in range(20)]}
        self.check_failure_preserves_snapshot(source,{str(i):f for i in range(18)},"coverage below 95%")

    def test_different_session_cannot_overwrite_snapshot(self):
        f=bars([100.]*120)
        source={"last_trading_date":str((f.index[-1]+pd.offsets.BDay()).date()),
                "rows":[{"symbol":"ONE"}]}
        self.check_failure_preserves_snapshot(source,{"ONE":f},"does not match")
