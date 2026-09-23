from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from tae2 import data

# 2026-09-23 at 10:00 and 17:00 New York time.
BEFORE_CLOSE = datetime(2026, 9, 23, 14, 0, tzinfo=timezone.utc)
AFTER_CLOSE = datetime(2026, 9, 23, 21, 0, tzinfo=timezone.utc)


def _prices(last: str, cols=("SPY", "IEF")) -> pd.DataFrame:
    idx = pd.bdate_range(end=last, periods=30)
    return pd.DataFrame({c: np.linspace(100, 110, len(idx)) for c in cols}, index=idx)


class SessionTest(unittest.TestCase):
    def test_before_the_close_the_last_session_is_yesterday(self) -> None:
        self.assertEqual(data.last_closed_session(BEFORE_CLOSE), date(2026, 9, 22))

    def test_after_the_close_it_is_today(self) -> None:
        self.assertEqual(data.last_closed_session(AFTER_CLOSE), date(2026, 9, 23))

    def test_weekend_points_back_to_friday(self) -> None:
        sunday = datetime(2026, 9, 27, 15, 0, tzinfo=timezone.utc)
        self.assertEqual(data.last_closed_session(sunday), date(2026, 9, 25))


class ValidateTest(unittest.TestCase):
    def test_clean_series_has_no_issues(self) -> None:
        self.assertEqual(data.validate(_prices("2026-09-22"), BEFORE_CLOSE), [])

    def test_missing_previous_session_bar_is_stale(self) -> None:
        # The 2026-09-23 incident: Yahoo had no bar for 2026-09-22.
        kinds = {(i.ticker, i.kind) for i in data.validate(_prices("2026-09-21"), BEFORE_CLOSE)}
        self.assertEqual(kinds, {("SPY", "STALE"), ("IEF", "STALE")})

    def test_gap_jump_and_non_positive_are_reported(self) -> None:
        p = _prices("2026-09-22")
        p.iloc[5:10, 1] = np.nan  # 5 missing days in IEF
        p.iloc[20, 0] = p.iloc[19, 0] * 1.5  # SPY +50% in a day
        p.iloc[25, 1] = 0.0
        kinds = {(i.ticker, i.kind) for i in data.validate(p, BEFORE_CLOSE)}
        self.assertIn(("IEF", "GAP"), kinds)
        self.assertIn(("SPY", "JUMP"), kinds)
        self.assertIn(("IEF", "NON_POSITIVE"), kinds)

    def test_bar_for_an_open_session_is_flagged_and_dropped(self) -> None:
        p = _prices("2026-09-23")
        self.assertIn("PARTIAL_BAR", {i.kind for i in data.validate(p, BEFORE_CLOSE)})
        self.assertEqual(data.drop_unclosed_session(p, BEFORE_CLOSE).index[-1], pd.Timestamp("2026-09-22"))
        self.assertEqual(data.drop_unclosed_session(p, AFTER_CLOSE).index[-1], pd.Timestamp("2026-09-23"))


if __name__ == "__main__":
    unittest.main()
