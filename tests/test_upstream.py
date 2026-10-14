import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from wait_upstream import fresh, batch_cutoff


class UpstreamTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 14, 15, tzinfo=timezone.utc)
        self.cutoff = batch_cutoff(self.now)
        self.data = {"generated_at": "2026-10-14T19:50:00+05:30",
                     "refresh_batch": self.cutoff.isoformat(),
                     "last_trading_date": "2026-10-14", "rows": [{"symbol": "A"}]}

    def test_fresh_batch(self):
        self.assertTrue(fresh(self.data, self.cutoff, self.now))

    def test_reject_previous_batch_even_if_republished_now(self):
        self.data["refresh_batch"] = (self.cutoff - timedelta(days=1)).isoformat()
        self.assertFalse(fresh(self.data, self.cutoff, self.now))

    def test_reject_naive_or_old_or_future_generation(self):
        for timestamp in ("2026-10-14T19:50:00", "2026-10-13T20:00:00+05:30",
                          "2026-10-15T20:00:00+05:30", "invalid"):
            self.data["generated_at"] = timestamp
            self.assertFalse(fresh(self.data, self.cutoff, self.now))

    def test_reject_missing_metadata_and_empty(self):
        self.assertFalse(fresh({}, self.cutoff, self.now))
        self.data["rows"] = []
        self.assertFalse(fresh(self.data, self.cutoff, self.now))

    def test_ist_schedule_maps_to_utc_and_before_cutoff(self):
        self.assertEqual(self.cutoff.hour, 14)
        before = datetime(2026, 10, 14, 13, 59, tzinfo=timezone.utc)
        self.assertEqual(batch_cutoff(before).day, 13)
