import unittest
from core.earnings_state import determine_earnings_state, compute_eps_yoy

class TestEarningsState(unittest.TestCase):
    def setUp(self):
        # Mock rules
        self.rules = {
            "earnings_state": {
                "thresholds": {
                    "growth_strong": 0.15,
                    "growth_moderate": 0.05,
                    "decline_mild": -0.05,
                    "decline_deep": -0.20
                },
                "min_trend_quarters": 2,
                "labels": {
                    "E0": {"label_zh": "无", "desc_zh": "无"},
                    "E1": {"label_zh": "扩张", "desc_zh": "扩张"},
                    "E2": {"label_zh": "稳定", "desc_zh": "稳定"},
                    "E3": {"label_zh": "放缓", "desc_zh": "放缓"},
                    "E4": {"label_zh": "下滑", "desc_zh": "下滑"},
                    "E5": {"label_zh": "亏损", "desc_zh": "亏损/深度"},
                    "E6": {"label_zh": "修复", "desc_zh": "修复"}
                }
            }
        }
        
    def test_compute_yoy(self):
        # Data: Date, Value
        # Q1, Q2, Q3, Q4, Q1_next
        series = [
            ("20200331", 1.0),
            ("20200630", 1.1),
            ("20200930", 1.2),
            ("20201231", 1.3),
            ("20210331", 1.5), # YoY = (1.5-1.0)/1.0 = 0.5
        ]
        yoy = compute_eps_yoy(series)
        expected = ("20210331", 0.5)
        self.assertIn(expected, yoy)
        
    def test_e1_strong_growth(self):
        # Strong growth for last 2 quarters
        # Need enough history for 3 YoY points
        # History: 2018-2019 Base, 2020 growth
        series = [
            ("20190331", 1.0), ("20190630", 1.0), ("20190930", 1.0), ("20191231", 1.0),
            ("20200331", 1.2), ("20200630", 1.25), ("20200930", 1.3), ("20201231", 1.4)
        ]
        info = determine_earnings_state(series, self.rules)
        self.assertEqual(info.code, "E1")
    
    def test_e5_loss(self):
        # Latest negative
        series = [
            ("20190331", 1.0), ("20190630", 1.0), ("20190930", 1.0), ("20191231", 1.0),
            ("20200331", 1.0), ("20200630", 1.0), ("20200930", 1.0), ("20210331", -0.5)
        ]
        info = determine_earnings_state(series, self.rules)
        self.assertEqual(info.code, "E5")

    def test_e6_recovery(self):
        # Was negative growth, now positive
        # Year 1: 1.0, 1.0
        # Year 2: 0.8 (-20%), 0.6 (-40%) -> Bad
        # Year 3: 0.7 (+16% vs 0.6?), 0.9 (+12% vs 0.8)
        # Let's construct explicitly
        series = [
            # Base
            ("20200331", 1.0), ("20200630", 1.0),
            # Decline phase
            ("20210331", 0.8), ("20210630", 0.6), # YoY: -0.2, -0.4
            # Recovery phase
            ("20220331", 0.9), ("20220630", 0.8)  # YoY: (0.9-0.8)/0.8=+0.125, (0.8-0.6)/0.6=+0.33
        ]
        info = determine_earnings_state(series, self.rules)
        # Last 2 YoY are > 0. Previous (2021) were < 0.
        self.assertEqual(info.code, "E6")

if __name__ == '__main__':
    unittest.main()
