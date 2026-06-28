"""
Accounting package — Phase IX Sprint IX.2A integration hub.

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Canonical accounting kernel: independent_double_entry.py
All consumers should read tae_independent_double_entry_verification.json.
"""

from research_core.accounting.independent_double_entry import (
    CANONICAL_KERNEL_MODULE,
    CANONICAL_SCHEMA,
    DEFAULT_JSON_PATH as DEFAULT_INDEPENDENT_JSON_PATH,
    DEFAULT_TXT_PATH as DEFAULT_INDEPENDENT_TXT_PATH,
    IndependentDoubleEntryVerifier,
    load_canonical_verification,
)
from research_core.accounting.ledger_audit import CashFlowLedgerAuditor
from research_core.accounting.ledger_report import (
    ANALYSIS_SAFETY_BANNER,
    CANONICAL_ACCOUNT_VALUE_SOURCE,
    DEFAULT_LEDGER_JSON_PATH,
    DEFAULT_LEDGER_TXT_PATH,
    LedgerAuditReport,
    LedgerReportStore,
    LedgerStatus,
    RECONCILIATION_FORMULA,
)

__all__ = [
    "ANALYSIS_SAFETY_BANNER",
    "CANONICAL_ACCOUNT_VALUE_SOURCE",
    "CANONICAL_KERNEL_MODULE",
    "CANONICAL_SCHEMA",
    "CashFlowLedgerAuditor",
    "DEFAULT_INDEPENDENT_JSON_PATH",
    "DEFAULT_INDEPENDENT_TXT_PATH",
    "DEFAULT_LEDGER_JSON_PATH",
    "DEFAULT_LEDGER_TXT_PATH",
    "IndependentDoubleEntryVerifier",
    "LedgerAuditReport",
    "LedgerReportStore",
    "LedgerStatus",
    "RECONCILIATION_FORMULA",
    "load_canonical_verification",
]
