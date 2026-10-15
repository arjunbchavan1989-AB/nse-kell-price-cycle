"""Display-order regressions; classifier precedence must remain unchanged."""
import ast
from pathlib import Path
import re
import unittest

class BoardOrderTests(unittest.TestCase):
    def setUp(self):
        html=(Path(__file__).resolve().parents[1]/"web/index.html").read_text()
        self.order=ast.literal_eval(re.search(r"BOARD_ORDER=new Map\((\[.*?\])\.map",html).group(1))

    def test_no_clear_setup_immediately_after_trend_holding(self):
        self.assertEqual(self.order.index("NC"),self.order.index("TR")+1)

    def test_trend_holding_still_immediately_after_exhaustion(self):
        self.assertEqual(self.order.index("TR"),self.order.index("EE")+1)

    def test_all_ten_lanes_preserved_in_requested_order(self):
        self.assertEqual(self.order,["RE","WP","CB","BB","EE","TR","NC","WD","BC","BD"])
