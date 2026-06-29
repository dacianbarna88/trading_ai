"""
TAE Advisory Index report persistence — Phase X Sprint X.7B
"""

from __future__ import annotations

import json
from pathlib import Path

from research_core.governance.advisory_index import (
    ADVISORY_INDEX_SAFETY_BANNER,
    AdvisoryIndexBuilder,
    AdvisoryIndexReport,
)

DEFAULT_JSON_PATH = Path("tae_advisory_index.json")


class AdvisoryIndexReportStore:
    def __init__(self, json_path: Path | None = None) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH

    @property
    def json_path(self) -> Path:
        return self._json_path

    def build(self, root: Path | str = ".") -> AdvisoryIndexReport:
        return AdvisoryIndexBuilder(root).build()

    def persist(self, report: AdvisoryIndexReport) -> Path:
        self._json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._json_path

    def build_and_persist(self, root: Path | str = ".") -> tuple[AdvisoryIndexReport, Path]:
        report = self.build(root)
        path = self.persist(report)
        return report, path

    def format_text(self, report: AdvisoryIndexReport) -> str:
        lines = [
            "===== TAE ADVISORY INDEX — SPRINT X.7B =====",
            "",
            f"Safety banner: {ADVISORY_INDEX_SAFETY_BANNER}",
            f"Mode: {report.mode}",
            f"Live trading impact: {report.live_trading_impact}",
            f"Generated: {report.generated_at.isoformat()}",
            "",
            "===== COUNTS =====",
            f"  Total reports: {report.total_reports}",
            f"  Valid reports: {report.valid_reports}",
            f"  Invalid reports: {report.invalid_reports}",
            "",
            "===== REPORTS BY CATEGORY =====",
        ]

        for category, files in report.reports_by_category.items():
            if not files:
                continue
            latest = report.latest_timestamp_by_category.get(category)
            lines.append(f"  {category}: {len(files)} (latest: {latest or 'n/a'})")

        if report.verdict_status_distribution:
            lines.extend(["", "===== VERDICT / STATUS DISTRIBUTION ====="])
            for verdict, count in report.verdict_status_distribution.items():
                lines.append(f"  {verdict}: {count}")

        if report.warnings_distribution:
            lines.extend(["", "===== WARNINGS DISTRIBUTION (top 10) ====="])
            for warning, count in list(report.warnings_distribution.items())[:10]:
                lines.append(f"  [{count}] {warning}")

        if report.advisory_notes:
            lines.extend(["", "===== ADVISORY NOTES ====="])
            for note in report.advisory_notes:
                lines.append(f"  • {note}")

        if report.invalid_report_details:
            lines.extend(["", "===== INVALID REPORT DETAILS ====="])
            for item in report.invalid_report_details:
                lines.append(
                    f"  • {item['report']} ({item['state']}): {item['error']}"
                )

        return "\n".join(lines)
