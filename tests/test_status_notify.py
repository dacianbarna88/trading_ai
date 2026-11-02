from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import portfolio_report as pr
import status_notify as sn

NOW = datetime(2026, 11, 2, 21, 5, tzinfo=timezone.utc)  # Mon 23:05 Bucharest (EET)


def _report(label="tae2", equity=100_000.0, cash=500.0, n=3, error=None):
    pos = [pr.PositionDetail(f"S{i}", 10, 1000.0 * (n - i), 100.0, 101.0) for i in range(n)]
    hist = [
        pr.EquityPoint(datetime(2026, 9, 22, tzinfo=timezone.utc), 100_000.0),
        pr.EquityPoint(datetime(2026, 11, 1, tzinfo=timezone.utc), 99_000.0),
        pr.EquityPoint(datetime(2026, 11, 2, tzinfo=timezone.utc), equity),
    ]
    return pr.AccountReport(label, equity, cash, pos, hist, error=error)


class BuildTest(unittest.TestCase):
    def _journals(self, d: Path, *entries):
        p = d / "runs.jsonl"
        p.write_text("".join(json.dumps(e) + "\n" for e in entries))
        return {"tae2": p, "stocks (MoVo10)": d / "missing.jsonl"}

    def test_evening_has_budget_positions_and_orders(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            j = self._journals(d, {"status": "submitted", "decision_date": "2026-10-30",
                                   "orders": [{}, {}, {}], "at": "2026-11-02T19:42:00+00:00"})
            s = sn.build([_report(equity=99_500.0, cash=497.12, n=4), _report("stocks (MoVo10)", n=71)],
                         "evening", NOW, j, d)
        self.assertIn("$497", s.short)
        self.assertIn("71 poz", s.short)
        self.assertIn("MoVo10", s.short)
        self.assertIn("Cash (buget liber): $497.12", s.long)
        self.assertIn("Poziții: **4**", s.long)
        self.assertIn("3 ordine trimise la 21:42", s.long)
        self.assertIn("Total combinat: $199,", s.long)
        self.assertIn("-0.50%", s.long)  # 99,000 -> 99,500 = +0.51%; since start -0.50%
        self.assertNotIn("⚠️", s.title)

    def test_morning_reports_the_health_verdict_and_failed_lines(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "system_health_2026-11-02.md").write_text(
                "- ✓ Teste: OK\n- ✗ PROBLEMĂ Rulare programată tae2: NU a rulat\n\n**Verdict: NECESITĂ ATENȚIE**\n")
            s = sn.build([_report()], "morning", datetime(2026, 11, 2, 8, 40, tzinfo=timezone.utc),
                         {"tae2": d / "nope"}, d)
        self.assertIn("NECESITĂ ATENȚIE", s.long)
        self.assertIn("NU a rulat", s.long)
        self.assertIn("⚠️", s.title)
        self.assertIn("1 probleme", s.short)

    def test_missing_health_report_is_said_not_hidden(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            s = sn.build([_report()], "morning", NOW, {"tae2": d / "nope"}, d)
        self.assertIn("lipsește", s.long)

    def test_unreadable_account_is_flagged_and_not_summed(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            bad = pr.AccountReport("stocks (MoVo10)", 0.0, 0.0, [], error="DNS")
            s = sn.build([_report(), bad], "evening", NOW,
                         {"tae2": d / "n", "stocks (MoVo10)": d / "n"}, d)
        self.assertIn("MoVo10: eroare", s.short)
        self.assertIn("⚠️", s.title)
        self.assertIn("Total combinat: $100,000.00", s.long)

    def test_no_run_today_says_so(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            s = sn.build([_report()], "evening", NOW, {"tae2": d / "n"}, d)
        self.assertIn("nicio rulare azi", s.long)


if __name__ == "__main__":
    unittest.main()
