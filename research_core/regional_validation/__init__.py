"""Regional validation gap closure — Phase VI Sprint B5 (read-only analysis)."""

from research_core.regional_validation.regional_gap_closure import RegionalGapClosureAnalyzer
from research_core.regional_validation.regional_validation_report import (
    DEFAULT_REGIONAL_JSON_PATH,
    DEFAULT_REGIONAL_TXT_PATH,
    RegionalValidationReport,
    RegionalValidationStore,
    TARGET_CANDIDATE_ID,
)

__all__ = [
    "DEFAULT_REGIONAL_JSON_PATH",
    "DEFAULT_REGIONAL_TXT_PATH",
    "RegionalGapClosureAnalyzer",
    "RegionalValidationReport",
    "RegionalValidationStore",
    "TARGET_CANDIDATE_ID",
]
