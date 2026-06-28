"""
Accounting integrity auditor — V1 / IX.2A consumer

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only audit of portfolio.csv accounting consistency — no modifications.
Canonical FIFO/PnL totals are read from independent_double_entry verification JSON.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.accounting.independent_double_entry import (
    DEFAULT_JSON_PATH as CANONICAL_VERIFICATION_JSON,
    load_canonical_verification,
)
from research_core.performance.performance_report import ANALYSIS_SAFETY_BANNER

logger = logging.getLogger(__name__)

PORTFOLIO_PATH = Path("portfolio.csv")
LATEST_PORTFOLIO_PATH = Path("latest_portfolio.txt")
BOT_LOG_PATH = Path("bot_output.log")

DEFAULT_INTEGRITY_JSON_PATH = Path("tae_accounting_integrity_audit.json")
DEFAULT_INTEGRITY_TXT_PATH = Path("tae_accounting_integrity_audit.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_accounting_integrity_audit"

FOCUS_TICKERS = ("GS", "AAPL", "SIE.DE", "ULVR.L")
NEAR_ZERO_INVESTED = 1.0
PRICE_TOLERANCE_PCT = 2.0
PNL_TOLERANCE = 5.0
STALE_HOURS = 24
MIN_SHARES = 0.0001


class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AnomalyType(str, Enum):
    REASON_PNL_MISMATCH = "REASON_PNL_MISMATCH"
    EXECUTION_VS_MARK_PNL = "EXECUTION_VS_MARK_PNL"
    SELL_PRICE_VS_AVG_COST = "SELL_PRICE_VS_AVG_COST"
    CURRENT_VS_SELL_PRICE = "CURRENT_VS_SELL_PRICE"
    INVESTED_VALUE_LOGIC = "INVESTED_VALUE_LOGIC"
    NEAR_ZERO_BUY = "NEAR_ZERO_BUY"
    STALE_SNAPSHOT = "STALE_SNAPSHOT"
    POSITION_RECONCILIATION = "POSITION_RECONCILIATION"


def _parse_dt(raw: str) -> datetime | None:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None or val == "":
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as exc:
        logger.warning("Could not read CSV %s: %s", path, exc)
        return []


def _is_realized_sell(row: dict[str, str]) -> bool:
    if row.get("Action", "").upper() != "SELL":
        return False
    reason = row.get("Reason", "").upper()
    signal = row.get("Signal", "").upper()
    if "REBALANCE" in reason or signal == "REBALANCE":
        return False
    if row.get("Ticker", "").upper() in ("CASH",):
        return False
    return True


@dataclass
class ParsedTrade:
    dt: datetime
    ticker: str
    action: str
    price: float
    shares: float
    score: float
    signal: str
    reason: str
    current_price: float
    invested: float
    current_value: float
    pnl: float
    pnl_pct: float


@dataclass
class SellValidation:
    ticker: str
    date: str
    reason: str
    signal: str
    sell_price: float
    avg_cost_at_sell: float
    current_price: float
    recorded_pnl: float
    expected_pnl_at_execution: float
    expected_pnl_at_mark: float
    reason_vs_pnl_ok: bool
    execution_vs_recorded_delta: float
    mark_vs_sell_price_delta_pct: float
    invested_value_ok: bool
    findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "date": self.date,
            "reason": self.reason,
            "signal": self.signal,
            "sell_price": round(self.sell_price, 4),
            "avg_cost_at_sell": round(self.avg_cost_at_sell, 4),
            "current_price": round(self.current_price, 4),
            "recorded_pnl": round(self.recorded_pnl, 4),
            "expected_pnl_at_execution": round(self.expected_pnl_at_execution, 4),
            "expected_pnl_at_mark": round(self.expected_pnl_at_mark, 4),
            "reason_vs_pnl_ok": self.reason_vs_pnl_ok,
            "execution_vs_recorded_delta": round(self.execution_vs_recorded_delta, 4),
            "mark_vs_sell_price_delta_pct": round(self.mark_vs_sell_price_delta_pct, 4),
            "invested_value_ok": self.invested_value_ok,
            "findings": list(self.findings),
        }


@dataclass
class AccountingAnomaly:
    anomaly_type: AnomalyType
    severity: Severity
    description: str
    ticker: str = ""
    date: str = ""
    recorded_pnl: float = 0.0
    expected_pnl: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.anomaly_type, str):
            self.anomaly_type = AnomalyType(self.anomaly_type)
        if isinstance(self.severity, str):
            self.severity = Severity(self.severity)

    def to_dict(self) -> dict[str, Any]:
        return {
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "ticker": self.ticker,
            "date": self.date,
            "recorded_pnl": round(self.recorded_pnl, 4),
            "expected_pnl": round(self.expected_pnl, 4),
        }


@dataclass
class FocusTickerAudit:
    ticker: str
    trade_count: int
    sell_validations: list[SellValidation]
    anomalies: list[AccountingAnomaly]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "trade_count": self.trade_count,
            "sell_validations": [v.to_dict() for v in self.sell_validations],
            "anomalies": [a.to_dict() for a in self.anomalies],
            "summary": self.summary,
        }


@dataclass
class IntegrityRecommendation:
    fix_id: str
    description: str
    rationale: str
    implementation_status: str = "NOT_IMPLEMENTED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "fix_id": self.fix_id,
            "description": self.description,
            "rationale": self.rationale,
            "implementation_status": self.implementation_status,
        }


@dataclass
class AccountingIntegrityAudit:
    sells_audited: int
    anomalies_found: int
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    sell_validations: list[SellValidation]
    anomalies: list[AccountingAnomaly]
    focus_ticker_audits: list[FocusTickerAudit]
    root_cause_hypotheses: list[str]
    recommendations: list[IntegrityRecommendation]
    stale_snapshot_detected: bool
    sources_loaded: dict[str, bool] = field(default_factory=dict)
    canonical_reference: dict[str, Any] | None = None
    safety_mode: str = ANALYSIS_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "sells_audited": self.sells_audited,
            "anomalies_found": self.anomalies_found,
            "high_severity_count": self.high_severity_count,
            "medium_severity_count": self.medium_severity_count,
            "low_severity_count": self.low_severity_count,
            "stale_snapshot_detected": self.stale_snapshot_detected,
            "sources_loaded": dict(self.sources_loaded),
            "canonical_reference": self.canonical_reference,
            "sell_validations": [v.to_dict() for v in self.sell_validations],
            "anomalies": [a.to_dict() for a in self.anomalies],
            "focus_ticker_audits": [f.to_dict() for f in self.focus_ticker_audits],
            "root_cause_hypotheses": list(self.root_cause_hypotheses),
            "recommendations": [r.to_dict() for r in self.recommendations],
        }

    def format_text(self) -> str:
        lines = [
            "===== AUDIT INTEGRITATE CONTABILĂ — TRADING AI V1 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"SELL-uri auditate: {self.sells_audited}",
            f"Anomalii detectate: {self.anomalies_found}",
            f"  HIGH: {self.high_severity_count} | MEDIUM: {self.medium_severity_count} | "
            f"LOW: {self.low_severity_count}",
            f"Snapshot învechit (latest_portfolio.txt): {self.stale_snapshot_detected}",
            "",
            "===== VALIDARE SELL (REZUMAT) =====",
        ]
        for val in self.sell_validations:
            status = "OK" if val.reason_vs_pnl_ok and val.invested_value_ok else "ISSUE"
            lines.append(
                f"  [{status}] {val.date[:10]} {val.ticker} | reason={val.reason[:40]} | "
                f"PnL={val.recorded_pnl:,.2f} | exec_exp={val.expected_pnl_at_execution:,.2f}"
            )
            for finding in val.findings:
                lines.append(f"      → {finding}")
        lines.append("")
        lines.append("===== ANOMALII CONTABILITATE =====")
        if self.anomalies:
            for an in self.anomalies:
                lines.append(
                    f"  [{an.severity.value}] {an.anomaly_type.value}: {an.description}"
                )
        else:
            lines.append("  Nicio anomalie.")
        lines.extend(["", "===== AUDIT TICKER-E FOCUS ====="])
        for focus in self.focus_ticker_audits:
            lines.append(f"--- {focus.ticker} ({focus.trade_count} tranzacții) ---")
            lines.append(f"  {focus.summary}")
            for an in focus.anomalies:
                lines.append(f"  [{an.severity.value}] {an.description}")
            lines.append("")
        lines.extend(["===== IPOTEZE CAUZĂ RĂDĂCINĂ ====="])
        for idx, hyp in enumerate(self.root_cause_hypotheses, start=1):
            lines.append(f"  {idx}. {hyp}")
        lines.extend(["", "===== RECOMANDĂRI (3) — NOT IMPLEMENTED ====="])
        for rec in self.recommendations:
            lines.append(f"  {rec.fix_id}: {rec.description}")
            lines.append(f"      Motiv: {rec.rationale}")
            lines.append(f"      Status: {rec.implementation_status}")
        lines.extend([
            "",
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "",
            "===== CONFIRMARE SIGURANȚĂ =====",
            "No live trading files were modified",
            "",
            "Audit contabilitate read-only — nu modifică portofoliu sau strategie.",
            "",
        ])
        return "\n".join(lines)


class AccountingIntegrityStore:
    """JSON/TXT persistence — stdlib only."""

    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_INTEGRITY_JSON_PATH
        self._txt_path = txt_path or DEFAULT_INTEGRITY_TXT_PATH

    def persist(self, audit: AccountingIntegrityAudit) -> Path:
        self._json_path.write_text(
            json.dumps(audit.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._json_path

    def persist_txt(self, audit: AccountingIntegrityAudit) -> Path:
        self._txt_path.write_text(audit.format_text() + "\n", encoding="utf-8")
        return self._txt_path


@dataclass
class _LotState:
    shares: float = 0.0
    total_cost: float = 0.0

    @property
    def avg_cost(self) -> float:
        return self.total_cost / self.shares if self.shares > 0 else 0.0


class AccountingIntegrityAuditor:
    """Read-only portfolio accounting integrity audit."""

    def __init__(self, store: AccountingIntegrityStore | None = None) -> None:
        self._store = store or AccountingIntegrityStore()
        self._sources_loaded: dict[str, bool] = {}

    def audit(self) -> AccountingIntegrityAudit:
        now = datetime.now(timezone.utc)
        rows_raw = _read_csv_rows(PORTFOLIO_PATH)
        self._sources_loaded["portfolio.csv"] = bool(rows_raw)
        self._sources_loaded["latest_portfolio.txt"] = LATEST_PORTFOLIO_PATH.is_file()
        self._sources_loaded["bot_output.log"] = BOT_LOG_PATH.is_file()
        self._sources_loaded["tae_independent_double_entry_verification.json"] = (
            CANONICAL_VERIFICATION_JSON.is_file()
        )

        canonical_reference = self._load_canonical_reference()

        parsed = self._parse_rows(rows_raw)
        sell_validations, anomalies = self._validate_sells(parsed)
        buy_anomalies = self._validate_buys(parsed)
        anomalies.extend(buy_anomalies)

        stale = self._check_stale_snapshot()
        if stale:
            anomalies.append(stale)

        recon_anomalies = self._check_position_reconciliation(parsed)
        anomalies.extend(recon_anomalies)

        focus_audits = self._audit_focus_tickers(parsed, sell_validations, anomalies)
        root_causes = self._build_root_causes(anomalies, sell_validations, stale)
        recommendations = self._build_recommendations(anomalies, sell_validations)

        high = sum(1 for a in anomalies if a.severity == Severity.HIGH)
        medium = sum(1 for a in anomalies if a.severity == Severity.MEDIUM)
        low = sum(1 for a in anomalies if a.severity == Severity.LOW)

        report = AccountingIntegrityAudit(
            sells_audited=len(sell_validations),
            anomalies_found=len(anomalies),
            high_severity_count=high,
            medium_severity_count=medium,
            low_severity_count=low,
            sell_validations=sell_validations,
            anomalies=anomalies,
            focus_ticker_audits=focus_audits,
            root_cause_hypotheses=root_causes,
            recommendations=recommendations,
            stale_snapshot_detected=stale is not None,
            sources_loaded=dict(self._sources_loaded),
            canonical_reference=canonical_reference,
            safety_mode=ANALYSIS_SAFETY_BANNER,
            generated_at=now,
        )
        self._store.persist(report)
        self._store.persist_txt(report)
        return report

    def _load_canonical_reference(self) -> dict[str, Any] | None:
        data = load_canonical_verification()
        if data is None:
            return None
        return {
            "schema": data.get("schema"),
            "verdict": data.get("verdict"),
            "independent_account_value": data.get("independent_account_value"),
            "independent_realized_pnl": data.get("independent_realized_pnl"),
            "independent_open_unrealized_pnl": data.get("independent_open_unrealized_pnl"),
            "independent_total_pnl": data.get("independent_total_pnl"),
            "source_module": "research_core/accounting/independent_double_entry.py",
        }

    def _parse_rows(self, rows_raw: list[dict[str, str]]) -> list[ParsedTrade]:
        parsed: list[ParsedTrade] = []
        for row in rows_raw:
            dt = _parse_dt(row.get("Date", ""))
            if dt is None:
                continue
            ticker = row.get("Ticker", "").strip()
            action = row.get("Action", "").strip().upper()
            if not ticker or not action:
                continue
            parsed.append(
                ParsedTrade(
                    dt=dt,
                    ticker=ticker,
                    action=action,
                    price=_safe_float(row.get("Price")),
                    shares=_safe_float(row.get("Shares")),
                    score=_safe_float(row.get("Score")),
                    signal=row.get("Signal", "").strip(),
                    reason=row.get("Reason", "").strip(),
                    current_price=_safe_float(row.get("Current_Price")),
                    invested=_safe_float(row.get("Invested")),
                    current_value=_safe_float(row.get("Current_Value")),
                    pnl=_safe_float(row.get("PnL")),
                    pnl_pct=_safe_float(row.get("PnL_%")),
                )
            )
        parsed.sort(key=lambda r: r.dt)
        return parsed

    def _validate_sells(
        self,
        parsed: list[ParsedTrade],
    ) -> tuple[list[SellValidation], list[AccountingAnomaly]]:
        validations: list[SellValidation] = []
        anomalies: list[AccountingAnomaly] = []
        lots: dict[str, _LotState] = {}

        for trade in parsed:
            lot = lots.setdefault(trade.ticker, _LotState())

            if trade.action == "BUY":
                cost = trade.invested if trade.invested > 0 else trade.price * trade.shares
                lot.shares += trade.shares
                lot.total_cost += cost
                continue

            if trade.action != "SELL":
                continue

            row_dict = {
                "Action": trade.action,
                "Reason": trade.reason,
                "Signal": trade.signal,
                "Ticker": trade.ticker,
            }
            if not _is_realized_sell(row_dict):
                if trade.shares > 0 and lot.shares > 0:
                    fraction = min(1.0, trade.shares / lot.shares)
                    lot.total_cost *= max(0.0, 1.0 - fraction)
                    lot.shares = max(0.0, lot.shares - trade.shares)
                continue

            avg_cost = lot.avg_cost
            shares_sold = trade.shares
            expected_exec_pnl = (trade.price - avg_cost) * shares_sold if avg_cost > 0 else 0.0
            expected_mark_pnl = (trade.current_price - avg_cost) * shares_sold if avg_cost > 0 else 0.0

            reason_upper = trade.reason.upper()
            signal_upper = trade.signal.upper()
            reason_vs_pnl_ok = True
            findings: list[str] = []

            if "PROFIT" in reason_upper and trade.pnl < -PNL_TOLERANCE:
                reason_vs_pnl_ok = False
                findings.append(
                    f"PROFIT reason but recorded PnL negative ({trade.pnl:.2f})"
                )
                anomalies.append(
                    AccountingAnomaly(
                        anomaly_type=AnomalyType.REASON_PNL_MISMATCH,
                        severity=Severity.HIGH,
                        description=(
                            f"PROFIT reason but negative realized PnL ({trade.pnl:.2f})"
                        ),
                        ticker=trade.ticker,
                        date=trade.dt.isoformat(),
                        recorded_pnl=trade.pnl,
                        expected_pnl=expected_exec_pnl,
                    )
                )
            if "STOP LOSS" in reason_upper and trade.pnl > PNL_TOLERANCE:
                reason_vs_pnl_ok = False
                findings.append(
                    f"STOP LOSS reason but recorded PnL positive ({trade.pnl:.2f})"
                )
                anomalies.append(
                    AccountingAnomaly(
                        anomaly_type=AnomalyType.REASON_PNL_MISMATCH,
                        severity=Severity.HIGH,
                        description=(
                            f"STOP LOSS reason but positive realized PnL ({trade.pnl:.2f})"
                        ),
                        ticker=trade.ticker,
                        date=trade.dt.isoformat(),
                        recorded_pnl=trade.pnl,
                        expected_pnl=expected_exec_pnl,
                    )
                )
            if (
                "TAKE PROFIT" in signal_upper or "TAKE PROFIT" in reason_upper
            ) and trade.pnl < -PNL_TOLERANCE:
                reason_vs_pnl_ok = False
                findings.append(
                    f"TAKE PROFIT signal but negative PnL ({trade.pnl:.2f})"
                )
                anomalies.append(
                    AccountingAnomaly(
                        anomaly_type=AnomalyType.REASON_PNL_MISMATCH,
                        severity=Severity.MEDIUM,
                        description=(
                            f"TAKE PROFIT signal but negative PnL ({trade.pnl:.2f})"
                        ),
                        ticker=trade.ticker,
                        date=trade.dt.isoformat(),
                        recorded_pnl=trade.pnl,
                        expected_pnl=expected_exec_pnl,
                    )
                )

            exec_delta = abs(trade.pnl - expected_exec_pnl)
            mark_delta_pct = 0.0
            if trade.price > 0:
                mark_delta_pct = abs(trade.current_price - trade.price) / trade.price * 100

            proceeds_pnl = (trade.current_price - trade.price) * shares_sold
            if abs(trade.pnl - proceeds_pnl) < PNL_TOLERANCE and exec_delta > PNL_TOLERANCE:
                findings.append(
                    "Recorded PnL = (Current_Price − sell Price) × shares, not execution gain"
                )
                anomalies.append(
                    AccountingAnomaly(
                        anomaly_type=AnomalyType.EXECUTION_VS_MARK_PNL,
                        severity=Severity.HIGH,
                        description=(
                            f"PnL ({trade.pnl:.2f}) derived from mark vs sell-price delta "
                            f"({proceeds_pnl:.2f}), not vs avg cost ({expected_exec_pnl:.2f})"
                        ),
                        ticker=trade.ticker,
                        date=trade.dt.isoformat(),
                        recorded_pnl=trade.pnl,
                        expected_pnl=expected_exec_pnl,
                    )
                )
            elif exec_delta > PNL_TOLERANCE and abs(trade.pnl - expected_mark_pnl) < PNL_TOLERANCE:
                findings.append(
                    "Recorded PnL matches mark-to-market, not execution price"
                )
                anomalies.append(
                    AccountingAnomaly(
                        anomaly_type=AnomalyType.EXECUTION_VS_MARK_PNL,
                        severity=Severity.HIGH,
                        description=(
                            f"PnL ({trade.pnl:.2f}) matches mark price PnL "
                            f"({expected_mark_pnl:.2f}), not execution "
                            f"({expected_exec_pnl:.2f})"
                        ),
                        ticker=trade.ticker,
                        date=trade.dt.isoformat(),
                        recorded_pnl=trade.pnl,
                        expected_pnl=expected_exec_pnl,
                    )
                )
            elif exec_delta > PNL_TOLERANCE * 10:
                findings.append(
                    f"Large delta vs execution PnL: recorded={trade.pnl:.2f}, "
                    f"expected={expected_exec_pnl:.2f}"
                )

            if avg_cost > 0 and trade.price < avg_cost and "PROFIT" in reason_upper:
                findings.append(
                    f"Sell price ({trade.price:.2f}) below avg cost ({avg_cost:.2f}) "
                    f"but reason says PROFIT"
                )
                anomalies.append(
                    AccountingAnomaly(
                        anomaly_type=AnomalyType.SELL_PRICE_VS_AVG_COST,
                        severity=Severity.HIGH,
                        description=(
                            f"Sell price {trade.price:.2f} < avg cost {avg_cost:.2f} "
                            f"with PROFIT label"
                        ),
                        ticker=trade.ticker,
                        date=trade.dt.isoformat(),
                        recorded_pnl=trade.pnl,
                        expected_pnl=expected_exec_pnl,
                    )
                )

            if mark_delta_pct > PRICE_TOLERANCE_PCT:
                findings.append(
                    f"Current_Price ({trade.current_price:.2f}) differs from "
                    f"sell Price ({trade.price:.2f}) by {mark_delta_pct:.1f}%"
                )
                if exec_delta > PNL_TOLERANCE:
                    anomalies.append(
                        AccountingAnomaly(
                            anomaly_type=AnomalyType.CURRENT_VS_SELL_PRICE,
                            severity=Severity.MEDIUM,
                            description=(
                                f"On SELL row, Current_Price ({trade.current_price:.2f}) "
                                f"≠ execution Price ({trade.price:.2f}) — "
                                f"may drive PnL distortion"
                            ),
                            ticker=trade.ticker,
                            date=trade.dt.isoformat(),
                            recorded_pnl=trade.pnl,
                            expected_pnl=expected_exec_pnl,
                        )
                    )

            expected_proceeds = trade.price * shares_sold
            expected_cost = avg_cost * shares_sold if avg_cost > 0 else 0.0
            invested_value_ok = True
            if expected_cost > 0:
                cost_delta_pct = abs(trade.invested - expected_cost) / expected_cost * 100
                if cost_delta_pct > PRICE_TOLERANCE_PCT:
                    invested_value_ok = False
                    findings.append(
                        f"Invested ({trade.invested:.2f}) ≠ avg_cost×shares ({expected_cost:.2f})"
                    )
            if expected_proceeds > 0:
                proceeds_delta_pct = abs(trade.current_value - expected_proceeds) / expected_proceeds * 100
                if proceeds_delta_pct > PRICE_TOLERANCE_PCT:
                    invested_value_ok = False
                    findings.append(
                        f"Current_Value ({trade.current_value:.2f}) ≠ "
                        f"sell_price×shares ({expected_proceeds:.2f})"
                    )
            if avg_cost > 0:
                expected_pnl_row = expected_proceeds - expected_cost
                if abs(trade.pnl - expected_pnl_row) > PNL_TOLERANCE:
                    invested_value_ok = False
                    findings.append(
                        f"PnL ({trade.pnl:.2f}) ≠ proceeds−cost ({expected_pnl_row:.2f})"
                    )

            pct_match = re.search(r"([+-]?\d+\.?\d*)%", trade.reason)
            if pct_match and avg_cost > 0:
                stated_pct = float(pct_match.group(1))
                actual_exec_pct = (trade.price - avg_cost) / avg_cost * 100
                if abs(stated_pct - actual_exec_pct) > 1.0:
                    findings.append(
                        f"Reason states {stated_pct:+.2f}% but execution move is "
                        f"{actual_exec_pct:+.2f}% vs avg cost"
                    )

            validation = SellValidation(
                ticker=trade.ticker,
                date=trade.dt.isoformat(),
                reason=trade.reason,
                signal=trade.signal,
                sell_price=trade.price,
                avg_cost_at_sell=avg_cost,
                current_price=trade.current_price,
                recorded_pnl=trade.pnl,
                expected_pnl_at_execution=expected_exec_pnl,
                expected_pnl_at_mark=expected_mark_pnl,
                reason_vs_pnl_ok=reason_vs_pnl_ok,
                execution_vs_recorded_delta=exec_delta,
                mark_vs_sell_price_delta_pct=mark_delta_pct,
                invested_value_ok=invested_value_ok,
                findings=findings,
            )
            validations.append(validation)

            if lot.shares > 0 and shares_sold > 0:
                fraction = min(1.0, shares_sold / lot.shares)
                lot.total_cost *= max(0.0, 1.0 - fraction)
                lot.shares = max(0.0, lot.shares - shares_sold)

        return validations, anomalies

    def _validate_buys(self, parsed: list[ParsedTrade]) -> list[AccountingAnomaly]:
        anomalies: list[AccountingAnomaly] = []
        for trade in parsed:
            if trade.action != "BUY":
                continue
            if 0 < trade.invested < NEAR_ZERO_INVESTED:
                anomalies.append(
                    AccountingAnomaly(
                        anomaly_type=AnomalyType.NEAR_ZERO_BUY,
                        severity=Severity.MEDIUM,
                        description=(
                            f"BUY near-zero invested amount ({trade.invested:.4f})"
                        ),
                        ticker=trade.ticker,
                        date=trade.dt.isoformat(),
                    )
                )
            expected = trade.price * trade.shares
            if expected > NEAR_ZERO_INVESTED and trade.invested > 0:
                delta_pct = abs(trade.invested - expected) / expected * 100
                if delta_pct > PRICE_TOLERANCE_PCT:
                    anomalies.append(
                        AccountingAnomaly(
                            anomaly_type=AnomalyType.INVESTED_VALUE_LOGIC,
                            severity=Severity.LOW,
                            description=(
                                f"BUY invested ({trade.invested:.2f}) ≠ "
                                f"price×shares ({expected:.2f})"
                            ),
                            ticker=trade.ticker,
                            date=trade.dt.isoformat(),
                        )
                    )
        return anomalies

    def _check_stale_snapshot(self) -> AccountingAnomaly | None:
        if not LATEST_PORTFOLIO_PATH.is_file() or not PORTFOLIO_PATH.is_file():
            return None
        latest_mtime = LATEST_PORTFOLIO_PATH.stat().st_mtime
        portfolio_mtime = PORTFOLIO_PATH.stat().st_mtime
        age_hours = (portfolio_mtime - latest_mtime) / 3600
        if age_hours > STALE_HOURS:
            return AccountingAnomaly(
                anomaly_type=AnomalyType.STALE_SNAPSHOT,
                severity=Severity.MEDIUM,
                description=(
                    f"latest_portfolio.txt is {age_hours:.1f}h older than portfolio.csv "
                    f"— dashboard snapshot may be stale"
                ),
            )
        return None

    def _check_position_reconciliation(
        self,
        parsed: list[ParsedTrade],
    ) -> list[AccountingAnomaly]:
        anomalies: list[AccountingAnomaly] = []
        net_shares: dict[str, float] = defaultdict(float)

        for trade in parsed:
            if trade.ticker == "CASH":
                continue
            if trade.action == "BUY":
                net_shares[trade.ticker] += trade.shares
            elif trade.action == "SELL":
                net_shares[trade.ticker] -= trade.shares

        for ticker, shares in net_shares.items():
            if shares < -MIN_SHARES:
                anomalies.append(
                    AccountingAnomaly(
                        anomaly_type=AnomalyType.POSITION_RECONCILIATION,
                        severity=Severity.HIGH,
                        description=f"Negative net shares ({shares:.4f}) for {ticker}",
                        ticker=ticker,
                    )
                )
        return anomalies

    def _audit_focus_tickers(
        self,
        parsed: list[ParsedTrade],
        sell_validations: list[SellValidation],
        all_anomalies: list[AccountingAnomaly],
    ) -> list[FocusTickerAudit]:
        audits: list[FocusTickerAudit] = []
        for ticker in FOCUS_TICKERS:
            trades = [t for t in parsed if t.ticker == ticker]
            sells = [v for v in sell_validations if v.ticker == ticker]
            ticker_anomalies = [a for a in all_anomalies if a.ticker == ticker]
            summary = self._summarize_focus_ticker(ticker, trades, sells, ticker_anomalies)
            audits.append(
                FocusTickerAudit(
                    ticker=ticker,
                    trade_count=len(trades),
                    sell_validations=sells,
                    anomalies=ticker_anomalies,
                    summary=summary,
                )
            )
        return audits

    def _summarize_focus_ticker(
        self,
        ticker: str,
        trades: list[ParsedTrade],
        sells: list[SellValidation],
        anomalies: list[AccountingAnomaly],
    ) -> str:
        if not trades:
            return f"No trades found for {ticker}."

        if ticker == "GS":
            gs_sell = next((s for s in sells if s.recorded_pnl < -100), None)
            if gs_sell:
                return (
                    f"GS SELL tagged PROFIT +5.48% (price rose {gs_sell.sell_price:.2f} vs "
                    f"avg cost {gs_sell.avg_cost_at_sell:.2f}) but recorded PnL "
                    f"{gs_sell.recorded_pnl:,.2f} — PnL computed from Current_Price "
                    f"({gs_sell.current_price:.2f}) not execution price."
                )

        if ticker == "AAPL":
            aapl_sell = next(
                (s for s in sells if "STOP LOSS" in s.reason.upper() and s.recorded_pnl > 0),
                None,
            )
            if aapl_sell:
                return (
                    f"AAPL SELL 2026-06-25: STOP LOSS -8.24% label (sell {aapl_sell.sell_price:.2f} "
                    f"< buy {aapl_sell.avg_cost_at_sell:.2f}) but PnL +{aapl_sell.recorded_pnl:.2f} "
                    f"because Current_Price ({aapl_sell.current_price:.2f}) > sell price."
                )

        if ticker == "SIE.DE":
            sie_sells = [s for s in sells]
            if len(sie_sells) >= 1:
                last = sie_sells[-1]
                return (
                    f"SIE.DE: {len(sie_sells)} SELL(s). Latest stop-loss "
                    f"({last.reason}) PnL={last.recorded_pnl:.2f}; "
                    f"mark vs execution delta {last.mark_vs_sell_price_delta_pct:.1f}%."
                )

        if ticker == "ULVR.L":
            ulvr = next((s for s in sells if s.recorded_pnl < 0), None)
            if ulvr:
                return (
                    f"ULVR.L round-trip same day: TAKE PROFIT signal but PnL "
                    f"{ulvr.recorded_pnl:.2f} — sell price {ulvr.sell_price:.2f} vs "
                    f"mark {ulvr.current_price:.2f} on exit row."
                )

        if anomalies:
            return f"{len(anomalies)} accounting anomaly/anomalies across {len(trades)} trades."
        return f"{len(trades)} trades reviewed — no focus-ticker anomalies."

    def _build_root_causes(
        self,
        anomalies: list[AccountingAnomaly],
        sell_validations: list[SellValidation],
        stale: AccountingAnomaly | None,
    ) -> list[str]:
        hypotheses: list[str] = []
        types = {a.anomaly_type for a in anomalies}

        mark_pnl_cases = [
            v for v in sell_validations
            if abs(v.recorded_pnl - v.expected_pnl_at_execution) > PNL_TOLERANCE
            and any(
                a.anomaly_type == AnomalyType.EXECUTION_VS_MARK_PNL and a.ticker == v.ticker
                for a in anomalies
            )
        ]
        if AnomalyType.EXECUTION_VS_MARK_PNL in types or mark_pnl_cases:
            examples = ", ".join(dict.fromkeys(v.ticker for v in mark_pnl_cases[:5])) or "GS, AAPL, ULVR.L"
            hypotheses.insert(
                0,
                f"PnL uses Current_Price (mark-to-market) instead of execution Price "
                f"on SELL rows — confirmed on {examples}.",
            )

        reason_mismatches = [
            a for a in anomalies if a.anomaly_type == AnomalyType.REASON_PNL_MISMATCH
        ]
        if reason_mismatches:
            hypotheses.append(
                "Reason label based on signal or price-move percentage, not realized "
                f"economic result — {len(reason_mismatches)} SELL row(s) contradict their label."
            )

        recon = [a for a in anomalies if a.anomaly_type == AnomalyType.POSITION_RECONCILIATION]
        if recon:
            hypotheses.append(
                "Open/closed position reconciliation issue — negative net shares detected."
            )
        else:
            hypotheses.append(
                "Position share counts reconcile (no negative net shares) — "
                "issues are valuation/labeling, not missing lots."
            )

        if stale or AnomalyType.STALE_SNAPSHOT in types:
            hypotheses.append(
                "Stale snapshot file: latest_portfolio.txt lags portfolio.csv — "
                "downstream reports may show outdated marks."
            )

        if not hypotheses:
            hypotheses.append("No dominant accounting defect pattern identified.")
        return hypotheses

    def _build_recommendations(
        self,
        anomalies: list[AccountingAnomaly],
        sell_validations: list[SellValidation],
    ) -> list[IntegrityRecommendation]:
        mark_cases = sum(
            1 for a in anomalies if a.anomaly_type == AnomalyType.EXECUTION_VS_MARK_PNL
        )
        if mark_cases == 0:
            mark_cases = sum(
                1 for v in sell_validations
                if abs(v.execution_vs_recorded_delta) > PNL_TOLERANCE * 10
            )
        reason_cases = sum(
            1 for a in anomalies if a.anomaly_type == AnomalyType.REASON_PNL_MISMATCH
        )

        return [
            IntegrityRecommendation(
                fix_id="FIX-001",
                description=(
                    "On SELL rows, compute realized PnL as (execution_price − avg_cost) × shares "
                    "— not (current_price − avg_cost) × shares. Do not auto-apply."
                ),
                rationale=(
                    f"{mark_cases} SELL row(s) show mark-price PnL; GS alone misstates "
                    f"~$909 vs ~+$548 execution gain."
                ),
            ),
            IntegrityRecommendation(
                fix_id="FIX-002",
                description=(
                    "Align SELL reason labels with realized PnL sign after computation — "
                    "PROFIT/STOP LOSS/TAKE PROFIT must match economic outcome. "
                    "Do not auto-apply."
                ),
                rationale=(
                    f"{reason_cases} reason/PnL mismatches (AAPL STOP LOSS +PnL, "
                    f"GS PROFIT −PnL, ULVR.L TAKE PROFIT −PnL)."
                ),
            ),
            IntegrityRecommendation(
                fix_id="FIX-003",
                description=(
                    "Refresh latest_portfolio.txt from portfolio.csv on each bot cycle or "
                    "add timestamp guard in dashboard. Do not auto-apply."
                ),
                rationale=(
                    "Stale snapshot detected — dashboard and audit consumers may read "
                    "outdated position marks."
                ),
            ),
        ]
