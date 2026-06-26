"""Profit attribution engine — Phase VII Sprint A1 (read-only analysis)."""

from research_core.profit_attribution.attribution_report import (
    DEFAULT_ATTRIBUTION_JSON_PATH,
    DEFAULT_ATTRIBUTION_TXT_PATH,
    AttributionVerdict,
    ProfitAttributionReport,
    AttributionReportStore,
    SAFETY_BANNER,
)
from research_core.profit_attribution.profit_attribution import ProfitAttributionEngine

__all__ = [
    "AttributionReportStore",
    "AttributionVerdict",
    "DEFAULT_ATTRIBUTION_JSON_PATH",
    "DEFAULT_ATTRIBUTION_TXT_PATH",
    "ProfitAttributionEngine",
    "ProfitAttributionReport",
    "SAFETY_BANNER",
]
