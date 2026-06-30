"""
TAE Live Advisory Bridge — Phase X Sprint X.7C

PAPER_ONLY | ADVISORY_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE

Read-only bridge: advisory index + live artifacts + selected tae reports → tae_live_advisory.json.
Does not modify live_bot.py, portfolio.csv, live_signals.csv, or trigger execution.
"""

from __future__ import annotations

import csv
import json
import logging
import socket
import statistics
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.governance.advisory_index import (
    TIMESTAMP_KEYS,
    VERDICT_KEYS,
    _extract_verdict,
    _extract_warnings,
)

logger = logging.getLogger(__name__)

LIVE_ADVISORY_SAFETY_BANNER = (
    "PAPER_ONLY | ADVISORY_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE"
)

DEFAULT_OUTPUT_PATH = Path("tae_live_advisory.json")
ADVISORY_INDEX_PATH = Path("tae_advisory_index.json")
PORTFOLIO_PATH = Path("portfolio.csv")
LIVE_SIGNALS_PATH = Path("live_signals.csv")
BOT_STATUS_PATH = Path("bot_status.txt")
DASHBOARD_STATUS_PATH = Path("dashboard_status.txt")
BOT_PID_PATH = Path("bot_pid.txt")
DASHBOARD_PID_PATH = Path("dashboard_pid.txt")
MARKET_MONITOR_PATH = Path("tae_market_open_monitor.json")
LIVE_BOT_PATH = Path("live_bot.py")
BOT_PGREP_PATTERN = "live_bot.py"
DASHBOARD_PGREP_PATTERN = "streamlit run dashboard_v2.py"
DASHBOARD_PORT = 8501

# Align with live_bot.py inline constants (does not import live_bot).
LIVE_STARTING_CAPITAL = 30000.0
LIVE_MAX_POSITIONS = 12
LIVE_MIN_BUY_SCORE = 80

RELEVANT_TAE_REPORTS = (
    "tae_quick_health_check.json",
    "tae_meta_intelligence.json",
    "tae_continuous_strategy_ranking.json",
    "tae_historical_results_analysis.json",
    "tae_strategic_performance_audit.json",
    "tae_full_ecosystem_run.json",
    "tae_ecosystem_orchestrator.json",
)

ADVISORY_ACTIONS = (
    "NO_ACTION",
    "BUY_ADVISORY",
    "SELL_ADVISORY",
    "RISK_ADVISORY",
)

QUICK_HEALTH_READY = frozenset(
    {
        "TAE_QUICK_HEALTH_READY",
        "TAE_QUICK_HEALTH_READY_WITH_WARNINGS",
    }
)

NEGATIVE_VERDICT_MARKERS = (
    "BLOCKED",
    "FAILED",
    "NOT_READY",
    "ANOMALY",
    "MISMATCH",
    "DISTORTION",
)

WARNING_CLASS_CRITICAL = "CRITICAL"
WARNING_CLASS_WARNING = "WARNING"
WARNING_CLASS_INFO = "INFO"
WARNING_CLASS_NORMAL_MARKET_CLOSED = "NORMAL_MARKET_CLOSED"
WARNING_CLASS_STALE_BUT_EXPECTED = "STALE_BUT_EXPECTED"
WARNING_CLASS_STALE_FALSE_POSITIVE = "STALE_FALSE_POSITIVE"

BLOCKING_WARNING_CLASSES = frozenset({WARNING_CLASS_CRITICAL, WARNING_CLASS_WARNING})
INFORMATIONAL_WARNING_CLASSES = frozenset(
    {
        WARNING_CLASS_INFO,
        WARNING_CLASS_NORMAL_MARKET_CLOSED,
        WARNING_CLASS_STALE_BUT_EXPECTED,
        WARNING_CLASS_STALE_FALSE_POSITIVE,
    }
)


def _pgrep(pattern: str) -> list[int]:
    for cmd in (["pgrep", "-f", pattern], ["/usr/bin/pgrep", "-f", pattern]):
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=5, check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if proc.returncode == 0 and proc.stdout.strip():
            return [
                int(x)
                for x in proc.stdout.strip().splitlines()
                if x.strip().isdigit()
            ]
    return []


def _port_open(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            return sock.connect_ex(("127.0.0.1", port)) == 0
    except OSError:
        return False


def _read_status_file(path: Path) -> str:
    if not path.is_file():
        return "UNKNOWN"
    return path.read_text(encoding="utf-8", errors="replace").strip() or "UNKNOWN"


def _pid_alive(path: Path) -> tuple[int | None, bool]:
    if not path.is_file():
        return None, False
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text.isdigit():
        return None, False
    pid = int(text)
    try:
        import os

        os.kill(pid, 0)
        return pid, True
    except OSError:
        return pid, False


def _probe_runtime_processes(root: Path) -> tuple[dict[str, Any], list[str]]:
    """
    Live process evidence for advisory warning reclassification.

    Direct pgrep/port checks take priority; monitor JSON supplements when present.
    """
    evidence_used: list[str] = []

    bot_pgrep = _pgrep(BOT_PGREP_PATTERN)
    dash_pgrep = _pgrep(DASHBOARD_PGREP_PATTERN)
    dash_port = _port_open(DASHBOARD_PORT)
    if bot_pgrep:
        evidence_used.append(f"pgrep:{BOT_PGREP_PATTERN}={bot_pgrep}")
    if dash_pgrep:
        evidence_used.append(f"pgrep:{DASHBOARD_PGREP_PATTERN}={dash_pgrep}")
    if dash_port:
        evidence_used.append(f"port:{DASHBOARD_PORT}=open")

    bot_status_file = _read_status_file(root / BOT_STATUS_PATH)
    dash_status_file = _read_status_file(root / DASHBOARD_STATUS_PATH)
    bot_pid, bot_pid_alive = _pid_alive(root / BOT_PID_PATH)
    dash_pid, dash_pid_alive = _pid_alive(root / DASHBOARD_PID_PATH)

    if bot_status_file != "UNKNOWN":
        evidence_used.append(f"bot_status.txt={bot_status_file}")
    if dash_status_file != "UNKNOWN":
        evidence_used.append(f"dashboard_status.txt={dash_status_file}")
    if bot_pid_alive:
        evidence_used.append(f"bot_pid.txt={bot_pid}:alive")
    if dash_pid_alive:
        evidence_used.append(f"dashboard_pid.txt={dash_pid}:alive")

    monitor_path = root / MARKET_MONITOR_PATH
    monitor_process: dict[str, Any] | None = None
    if monitor_path.is_file():
        monitor_payload, _err = _load_json(monitor_path)
        if monitor_process := (monitor_payload or {}).get("process"):
            if isinstance(monitor_process, dict):
                evidence_used.append("tae_market_open_monitor.json:process")

    if bot_pgrep or bot_pid_alive or str(bot_status_file).upper() == "RUNNING":
        bot_effective = "RUNNING"
    elif str(bot_status_file).upper() == "STOPPED":
        bot_effective = "STOPPED"
    elif monitor_process and monitor_process.get("bot_effective"):
        bot_effective = str(monitor_process["bot_effective"]).upper()
        evidence_used.append("monitor:bot_effective")
    else:
        bot_effective = str(bot_status_file).upper() or "UNKNOWN"

    if dash_port or dash_pgrep or dash_pid_alive or str(dash_status_file).upper() == "RUNNING":
        dash_effective = "RUNNING"
    elif str(dash_status_file).upper() == "STOPPED":
        dash_effective = "STOPPED"
    elif monitor_process and monitor_process.get("dashboard_effective"):
        dash_effective = str(monitor_process["dashboard_effective"]).upper()
        evidence_used.append("monitor:dashboard_effective")
    else:
        dash_effective = str(dash_status_file).upper() or "UNKNOWN"

    return (
        {
            "bot_status_file": bot_status_file,
            "bot_status_effective": bot_effective,
            "bot_process_pgrep_pids": bot_pgrep,
            "bot_pid": bot_pid,
            "bot_pid_alive": bot_pid_alive,
            "dashboard_status_file": dash_status_file,
            "dashboard_status_effective": dash_effective,
            "dashboard_pgrep_pids": dash_pgrep,
            "dashboard_port_8501_open": dash_port,
            "dashboard_pid": dash_pid,
            "dashboard_pid_alive": dash_pid_alive,
        },
        evidence_used,
    )


def _classify_warning(
    text: str,
    *,
    markets_open: bool | None = None,
    runtime: dict[str, Any] | None = None,
) -> str:
    """Classify advisory warning for BUY-block weighting."""
    lowered = str(text).lower()
    runtime = runtime or {}

    bot_effective = str(
        runtime.get("bot_status_effective") or runtime.get("bot_status") or ""
    ).upper()
    dash_effective = str(runtime.get("dashboard_status_effective") or "").upper()
    bot_pgrep = runtime.get("bot_process_pgrep_pids") or []
    dash_port = bool(runtime.get("dashboard_port_8501_open"))
    dash_pgrep = runtime.get("dashboard_pgrep_pids") or []

    if "bot process not detected" in lowered:
        if bot_effective == "RUNNING" or bot_pgrep:
            return WARNING_CLASS_STALE_FALSE_POSITIVE
        if markets_open is False:
            return WARNING_CLASS_NORMAL_MARKET_CLOSED
        if markets_open is True and bot_effective == "STOPPED":
            return WARNING_CLASS_WARNING
        if markets_open is True:
            return WARNING_CLASS_WARNING
        return WARNING_CLASS_NORMAL_MARKET_CLOSED

    if "dashboard/streamlit not detected" in lowered or (
        "dashboard" in lowered and "not detected" in lowered
    ):
        if dash_effective == "RUNNING" or dash_port or dash_pgrep:
            return WARNING_CLASS_STALE_FALSE_POSITIVE
        if markets_open is False:
            return WARNING_CLASS_NORMAL_MARKET_CLOSED
        if markets_open is True:
            return WARNING_CLASS_WARNING
        return WARNING_CLASS_INFO

    if "market closed" in lowered or "all_markets_closed" in lowered:
        return WARNING_CLASS_NORMAL_MARKET_CLOSED

    if "bot status: stopped" in lowered and markets_open is False:
        return WARNING_CLASS_NORMAL_MARKET_CLOSED

    if "git working tree" in lowered or "git dirty" in lowered:
        return WARNING_CLASS_INFO

    if "not duplicate portfolio" in lowered or "research metrics helper" in lowered:
        return WARNING_CLASS_INFO

    if "paper_only" in lowered and "warning only" in lowered:
        return WARNING_CLASS_NORMAL_MARKET_CLOSED

    if any(marker.lower() in lowered for marker in NEGATIVE_VERDICT_MARKERS):
        return WARNING_CLASS_CRITICAL

    if "invalid" in lowered and "json" in lowered:
        return WARNING_CLASS_CRITICAL

    if "missing" in lowered and any(
        token in lowered for token in ("json", "portfolio", "signals", "advisory")
    ):
        return WARNING_CLASS_WARNING

    if "below -3% pnl" in lowered or "outlier-driven" in lowered:
        return WARNING_CLASS_WARNING

    return WARNING_CLASS_INFO


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"invalid_json: {exc}"
    except OSError as exc:
        return None, f"read_error: {exc}"
    if not isinstance(payload, dict):
        return None, "invalid_root"
    return payload, None


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


@dataclass
class LiveAdvisoryReport:
    runtime_snapshot: dict[str, Any]
    tae_snapshot: dict[str, Any]
    action: str
    confidence: int
    reasons: list[str]
    blockers: list[str]
    blocking_warnings: list[str] = field(default_factory=list)
    informational_warnings: list[str] = field(default_factory=list)
    stale_false_positive_warnings: list[str] = field(default_factory=list)
    warning_audit: list[dict[str, Any]] = field(default_factory=list)
    runtime_evidence_used: list[str] = field(default_factory=list)
    relevant_reports: dict[str, Any] = field(default_factory=dict)
    live_bot_not_modified: bool = True
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def block_new_buy(self) -> bool:
        return self.action == "RISK_ADVISORY"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "tae.live_advisory.v1",
            "mode": "PAPER_ONLY_ADVISORY",
            "live_trading_impact": "NONE",
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": LIVE_ADVISORY_SAFETY_BANNER,
            "action": self.action,
            "block_new_buy": self.block_new_buy,
            "runtime_snapshot": dict(self.runtime_snapshot),
            "tae_snapshot": dict(self.tae_snapshot),
            "advisory": {
                "action": self.action,
                "confidence": self.confidence,
                "reasons": list(self.reasons),
                "blockers": list(self.blockers),
                "blocking_warnings": list(self.blocking_warnings),
                "informational_warnings": list(self.informational_warnings),
                "stale_false_positive_warnings": list(self.stale_false_positive_warnings),
                "blocking_warnings_count": len(self.blocking_warnings),
                "informational_warnings_count": len(self.informational_warnings),
                "stale_false_positive_warnings_count": len(
                    self.stale_false_positive_warnings
                ),
                "warning_audit": list(self.warning_audit),
                "runtime_evidence_used": list(self.runtime_evidence_used),
                "block_new_buy": self.block_new_buy,
            },
            "runtime_evidence_used": list(self.runtime_evidence_used),
            "relevant_reports_summary": self.relevant_reports,
            "safety": {
                "no_broker": True,
                "no_execution": True,
                "live_bot_not_modified": self.live_bot_not_modified,
                "advisory_only": True,
            },
        }


class LiveAdvisoryBridge:
    """Build read-only live advisory artifact from index + live CSV + TAE reports."""

    def __init__(self, root: Path | str = ".") -> None:
        self._root = Path(root)

    def _path(self, name: str | Path) -> Path:
        return self._root / name

    def _read_portfolio_rows(self) -> tuple[list[dict[str, str]], str | None]:
        path = self._path(PORTFOLIO_PATH)
        if not path.is_file():
            return [], "portfolio.csv missing"
        try:
            with path.open(encoding="utf-8", errors="replace", newline="") as handle:
                rows = list(csv.DictReader(handle))
        except OSError as exc:
            return [], f"portfolio.csv unreadable: {exc}"
        if not rows:
            return [], "portfolio.csv empty"
        return rows, None

    def _portfolio_snapshot(self) -> tuple[dict[str, Any], list[str]]:
        rows, error = self._read_portfolio_rows()
        blockers: list[str] = []
        if error:
            blockers.append(error)
            return {
                "open_positions_count": None,
                "portfolio_row_count": 0,
                "cash_available_usd": None,
                "losing_open_positions": 0,
                "portfolio_readable": False,
            }, blockers

        spent = 0.0
        received = 0.0
        deposited = 0.0
        positions: dict[str, dict[str, float]] = {}

        for row in rows:
            action = str(row.get("Action", "")).upper()
            ticker = str(row.get("Ticker", "")).strip().upper()
            price = _parse_float(row.get("Price")) or 0.0
            shares = _parse_float(row.get("Shares")) or 0.0

            if action == "BUY":
                spent += price * shares
                if ticker:
                    bucket = positions.setdefault(
                        ticker, {"buy_shares": 0.0, "sell_shares": 0.0, "buy_value": 0.0}
                    )
                    bucket["buy_shares"] += shares
                    bucket["buy_value"] += price * shares
            elif action == "SELL":
                received += price * shares
                if ticker:
                    bucket = positions.setdefault(
                        ticker, {"buy_shares": 0.0, "sell_shares": 0.0, "buy_value": 0.0}
                    )
                    bucket["sell_shares"] += shares
            elif action == "DEPOSIT":
                deposited += price * shares

        open_count = 0
        losing_open = 0
        for ticker, bucket in positions.items():
            open_shares = bucket["buy_shares"] - bucket["sell_shares"]
            if open_shares <= 0:
                continue
            open_count += 1
            pnl_pct = None
            for row in reversed(rows):
                if str(row.get("Ticker", "")).upper() != ticker:
                    continue
                if str(row.get("Action", "")).upper() != "BUY":
                    continue
                pnl_pct = _parse_float(row.get("PnL_%"))
                break
            if pnl_pct is not None and pnl_pct <= -3.0:
                losing_open += 1

        cash = LIVE_STARTING_CAPITAL + deposited - spent + received

        return {
            "open_positions_count": open_count,
            "portfolio_row_count": len(rows),
            "cash_available_usd": round(cash, 2),
            "losing_open_positions": losing_open,
            "portfolio_readable": True,
        }, blockers

    def _live_signals_snapshot(self) -> tuple[dict[str, Any], list[str]]:
        path = self._path(LIVE_SIGNALS_PATH)
        blockers: list[str] = []
        if not path.is_file():
            return {
                "latest_live_signal_count": 0,
                "strong_buy_signal_count": 0,
                "take_profit_signal_count": 0,
                "live_signals_present": False,
                "latest_signal_time": None,
            }, blockers

        try:
            with path.open(encoding="utf-8", errors="replace", newline="") as handle:
                rows = list(csv.DictReader(handle))
        except OSError as exc:
            blockers.append(f"live_signals.csv unreadable: {exc}")
            return {
                "latest_live_signal_count": 0,
                "strong_buy_signal_count": 0,
                "take_profit_signal_count": 0,
                "live_signals_present": False,
                "latest_signal_time": None,
            }, blockers

        strong_buy = 0
        take_profit = 0
        high_score_buys = 0
        latest_time = None
        historical_enriched = 0
        strong_buy_historical: list[dict[str, Any]] = []
        research_enriched = 0
        strong_buy_research: list[dict[str, Any]] = []
        committee_enriched = 0
        strong_buy_committee: list[dict[str, Any]] = []
        allocation_enriched = 0
        strong_buy_allocation: list[dict[str, Any]] = []
        meta_enriched = 0
        strong_buy_meta: list[dict[str, Any]] = []

        for row in rows:
            signal = str(row.get("Signal", "")).upper()
            score = _parse_float(row.get("Score")) or 0.0
            if signal == "STRONG BUY":
                strong_buy += 1
                if score >= LIVE_MIN_BUY_SCORE:
                    high_score_buys += 1
                if row.get("Historical_Edge"):
                    historical_enriched += 1
                    strong_buy_historical.append(
                        {
                            "ticker": str(row.get("Ticker") or "").upper(),
                            "edge": row.get("Historical_Edge"),
                            "win_rate": row.get("Historical_Win_Rate"),
                            "avg_return": row.get("Historical_Avg_Return"),
                            "sharpe": row.get("Historical_Sharpe"),
                            "strategy_rank": row.get("Strategy_Rank"),
                            "committee_score": row.get("Committee_Score"),
                            "historical_confidence": row.get("Historical_Confidence"),
                            "context": row.get("Recommendation_Context"),
                        }
                    )
                if row.get("Research_Confidence"):
                    research_enriched += 1
                    strong_buy_research.append(
                        {
                            "ticker": str(row.get("Ticker") or "").upper(),
                            "momentum": row.get("Research_Momentum"),
                            "sector": row.get("Research_Sector"),
                            "regional": row.get("Research_Regional"),
                            "macro": row.get("Research_Macro"),
                            "etf": row.get("Research_ETF"),
                            "threshold": row.get("Research_Threshold"),
                            "counterfactual": row.get("Research_Counterfactual"),
                            "confidence": row.get("Research_Confidence"),
                        }
                    )
                if row.get("Committee_Confidence"):
                    committee_enriched += 1
                    strong_buy_committee.append(
                        {
                            "ticker": str(row.get("Ticker") or "").upper(),
                            "decision": row.get("Committee_Decision"),
                            "confidence": row.get("Committee_Confidence"),
                            "weighted_score": row.get("Committee_Weighted_Score"),
                            "adaptive_weight": row.get("Committee_Adaptive_Weight"),
                            "accuracy": row.get("Committee_Accuracy"),
                            "votes": row.get("Committee_Votes"),
                        }
                    )
                if row.get("Allocation_Confidence"):
                    allocation_enriched += 1
                    strong_buy_allocation.append(
                        {
                            "ticker": str(row.get("Ticker") or "").upper(),
                            "allocation_score": row.get("Allocation_Score"),
                            "confidence": row.get("Allocation_Confidence"),
                            "region": row.get("Allocation_Region"),
                            "sector": row.get("Allocation_Sector"),
                            "macro": row.get("Allocation_Macro"),
                            "capital_flow": row.get("Capital_Flow"),
                            "bias": row.get("Allocation_Bias"),
                        }
                    )
                if row.get("Meta_Score"):
                    meta_enriched += 1
                    strong_buy_meta.append(
                        {
                            "ticker": str(row.get("Ticker") or "").upper(),
                            "meta_score": row.get("Meta_Score"),
                            "meta_confidence": row.get("Meta_Confidence"),
                            "meta_health": row.get("Meta_Health"),
                            "strategy_rank": row.get("Meta_Strategy_Rank"),
                            "ecosystem_status": row.get("Meta_Ecosystem_Status"),
                            "unified_runtime_score": row.get("Unified_Runtime_Score"),
                        }
                    )
            elif signal == "TAKE PROFIT":
                take_profit += 1
            ts = row.get("Time")
            if ts and (latest_time is None or str(ts) > str(latest_time)):
                latest_time = str(ts)

        return {
            "latest_live_signal_count": len(rows),
            "strong_buy_signal_count": strong_buy,
            "high_score_strong_buy_count": high_score_buys,
            "take_profit_signal_count": take_profit,
            "live_signals_present": True,
            "latest_signal_time": latest_time,
            "historical_enrichment_present": historical_enriched > 0,
            "historical_enriched_strong_buy_count": historical_enriched,
            "strong_buy_historical_summary": strong_buy_historical[:10],
            "research_enrichment_present": research_enriched > 0,
            "research_enriched_strong_buy_count": research_enriched,
            "strong_buy_research_summary": strong_buy_research[:10],
            "committee_enrichment_present": committee_enriched > 0,
            "committee_enriched_strong_buy_count": committee_enriched,
            "strong_buy_committee_summary": strong_buy_committee[:10],
            "allocation_enrichment_present": allocation_enriched > 0,
            "allocation_enriched_strong_buy_count": allocation_enriched,
            "strong_buy_allocation_summary": strong_buy_allocation[:10],
            "meta_enrichment_present": meta_enriched > 0,
            "meta_enriched_strong_buy_count": meta_enriched,
            "strong_buy_meta_summary": strong_buy_meta[:10],
        }, blockers

    def _bot_status(self) -> str:
        path = self._path(BOT_STATUS_PATH)
        if not path.is_file():
            return "UNKNOWN"
        return path.read_text(encoding="utf-8", errors="replace").strip() or "UNKNOWN"

    def _load_advisory_index(self) -> tuple[dict[str, Any] | None, str | None]:
        return _load_json(self._path(ADVISORY_INDEX_PATH))

    def _load_relevant_reports(self) -> dict[str, Any]:
        loaded: dict[str, Any] = {}
        for name in RELEVANT_TAE_REPORTS:
            payload, error = _load_json(self._path(name))
            loaded[name] = {
                "state": "ok" if payload is not None else error or "missing",
                "verdict": _extract_verdict(payload) if payload else None,
                "warnings": _extract_warnings(payload) if payload else [],
            }
            if payload:
                for key in TIMESTAMP_KEYS:
                    if payload.get(key):
                        loaded[name]["timestamp"] = payload.get(key)
                        break
        return loaded

    def _ssot(self) -> Any:
        if not hasattr(self, "_ssot_cache"):
            from research_core.meta_intelligence_runtime.unified_runtime_ssot import (
                UnifiedRuntimeSSOT,
            )

            self._ssot_cache = UnifiedRuntimeSSOT.load(self._root)
        return self._ssot_cache

    def _load_research_advisory_summary(self) -> dict[str, Any]:
        ssot = self._ssot()
        if ssot.ok:
            rows = ssot.records_with_signal("STRONG BUY")
            if rows:
                return {
                    "strong_buy_count": len(rows),
                    "avg_research_confidence": round(
                        sum(
                            float(r.get("Research_Confidence") or 0)
                            for r in rows
                            if r.get("Research_Confidence") is not None
                        )
                        / max(
                            1,
                            sum(1 for r in rows if r.get("Research_Confidence") is not None),
                        ),
                        2,
                    ),
                    "source": "tae_unified_runtime.json",
                }
        # LEGACY_RUNTIME_SOURCE
        enrich_path = self._path("tae_live_signals_research_enrich.json")
        payload, _ = _load_json(enrich_path)
        if payload and payload.get("advisory_summary"):
            return payload["advisory_summary"]
        try:
            from research_core.research_runtime.live_signals_enricher import ResearchContext

            return ResearchContext.load(self._root).advisory_summary()
        except Exception:
            return {}

    def _load_committee_advisory_summary(self) -> dict[str, Any]:
        ssot = self._ssot()
        if ssot.ok:
            rows = ssot.records_with_signal("STRONG BUY")
            top = sorted(
                rows,
                key=lambda r: float(r.get("Committee_Confidence") or 0),
                reverse=True,
            )[:10]
            if top:
                return {
                    "committee_summary": top[0].get("Committee_Decision"),
                    "committee_confidence": top[0].get("Committee_Confidence"),
                    "highest_confidence_candidates": [
                        {
                            "ticker": r.get("Ticker"),
                            "committee_decision": r.get("Committee_Decision"),
                            "committee_confidence": r.get("Committee_Confidence"),
                        }
                        for r in top
                    ],
                    "source": "tae_unified_runtime.json",
                }
        # LEGACY_RUNTIME_SOURCE
        enrich_path = self._path("tae_live_signals_committee_enrich.json")
        payload, _ = _load_json(enrich_path)
        if payload and payload.get("advisory_summary"):
            return payload["advisory_summary"]
        # LEGACY_RUNTIME_SOURCE — tae_committee_runtime.json
        runtime_path = self._path("tae_committee_runtime.json")
        runtime_payload, _ = _load_json(runtime_path)
        if runtime_payload and runtime_payload.get("advisory_summary"):
            return runtime_payload["advisory_summary"]
        try:
            from research_core.committee_runtime.live_signals_enricher import CommitteeContext

            return CommitteeContext.load(self._root).advisory_summary()
        except Exception:
            return {}

    def _load_allocation_advisory_summary(self) -> dict[str, Any]:
        ssot = self._ssot()
        if ssot.ok:
            rows = ssot.records_with_signal("STRONG BUY")
            if rows:
                return {
                    "allocation_score_avg": round(
                        sum(float(r.get("Allocation_Score") or 0) for r in rows) / len(rows),
                        2,
                    ),
                    "allocation_confidence_avg": round(
                        sum(float(r.get("Allocation_Confidence") or 0) for r in rows)
                        / len(rows),
                        2,
                    ),
                    "source": "tae_unified_runtime.json",
                }
        # LEGACY_RUNTIME_SOURCE
        enrich_path = self._path("tae_live_signals_allocation_enrich.json")
        payload, _ = _load_json(enrich_path)
        if payload and payload.get("advisory_summary"):
            return payload["advisory_summary"]
        # LEGACY_RUNTIME_SOURCE — tae_strategic_allocation_runtime.json
        runtime_path = self._path("tae_strategic_allocation_runtime.json")
        runtime_payload, _ = _load_json(runtime_path)
        if runtime_payload and runtime_payload.get("advisory_summary"):
            return runtime_payload["advisory_summary"]
        try:
            from research_core.strategic_allocation_runtime.live_signals_enricher import (
                AllocationContext,
            )

            return AllocationContext.load(self._root).advisory_summary()
        except Exception:
            return {}

    def _load_meta_advisory_summary(self) -> dict[str, Any]:
        ssot = self._ssot()
        if ssot.ok:
            rows = ssot.records_with_signal("STRONG BUY")
            if rows:
                return {
                    "meta_health": rows[0].get("Meta_Health"),
                    "meta_ecosystem_status": rows[0].get("Meta_Ecosystem_Status"),
                    "meta_score_avg": round(
                        sum(float(r.get("Meta_Score") or 0) for r in rows) / len(rows),
                        2,
                    ),
                    "source": "tae_unified_runtime.json",
                }
        # LEGACY_RUNTIME_SOURCE
        enrich_path = self._path("tae_live_signals_meta_enrich.json")
        payload, _ = _load_json(enrich_path)
        if payload and payload.get("advisory_summary"):
            return payload["advisory_summary"]
        # LEGACY_RUNTIME_SOURCE — tae_meta_intelligence_runtime.json
        runtime_path = self._path("tae_meta_intelligence_runtime.json")
        runtime_payload, _ = _load_json(runtime_path)
        if runtime_payload and runtime_payload.get("advisory_summary"):
            return runtime_payload["advisory_summary"]
        try:
            from research_core.meta_intelligence_runtime.live_signals_enricher import MetaContext

            return MetaContext.load(self._root).advisory_summary()
        except Exception:
            return {}

    def _load_unified_runtime_summary(self) -> dict[str, Any]:
        payload, _ = _load_json(self._path("tae_unified_runtime.json"))
        if payload and payload.get("advisory_summary"):
            return payload["advisory_summary"]
        try:
            from research_core.meta_intelligence_runtime.unified_runtime_builder import (
                build_unified_runtime,
            )

            return build_unified_runtime(self._root).get("advisory_summary") or {}
        except Exception:
            return {}

    def _load_strategy_advisory_summary(self) -> dict[str, Any]:
        ssot = self._ssot()
        block = ssot.section("strategy")
        if block:
            return block
        # LEGACY_RUNTIME_SOURCE
        sim_path = self._path("tae_strategy_simulation_runtime.json")
        payload, _ = _load_json(sim_path)
        if payload and payload.get("advisory_summary"):
            return payload["advisory_summary"]
        disc_path = self._path("tae_strategy_discovery_runtime.json")
        disc_payload, _ = _load_json(disc_path)
        if disc_payload and disc_payload.get("advisory_summary"):
            summary = dict(disc_payload["advisory_summary"])
            summary.setdefault("top_simulated_strategies", [])
            return summary
        try:
            from research_core.strategy_simulation_runtime.strategy_context import StrategyContext

            return StrategyContext.load(self._root).advisory_summary()
        except Exception:
            return {}

    def _load_event_memory_summary(self) -> dict[str, Any]:
        ssot = self._ssot()
        block = ssot.event_memory_summary()
        if block:
            return block
        # LEGACY_RUNTIME_SOURCE
        payload, _ = _load_json(self._path("tae_event_memory_runtime.json"))
        if payload and payload.get("advisory_summary"):
            return payload["advisory_summary"]
        try:
            from research_core.counterfactual_runtime.counterfactual_context import CounterfactualContext

            return CounterfactualContext.load(self._root).advisory_summary()
        except Exception:
            return {}

    def _load_counterfactual_summary(self) -> dict[str, Any]:
        ssot = self._ssot()
        block = ssot.section("counterfactual")
        if block:
            return block
        # LEGACY_RUNTIME_SOURCE
        payload, _ = _load_json(self._path("tae_counterfactual_runtime.json"))
        if payload and payload.get("advisory_summary"):
            return payload["advisory_summary"]
        try:
            from research_core.counterfactual_runtime.counterfactual_context import CounterfactualContext

            return CounterfactualContext.load(self._root).advisory_summary()
        except Exception:
            return {}

    def _load_ecosystem_summary(self) -> dict[str, Any]:
        ssot = self._ssot()
        block = ssot.section("ecosystem")
        if block:
            return block
        # LEGACY_RUNTIME_SOURCE
        payload, _ = _load_json(self._path("tae_ecosystem_runtime.json"))
        if payload and payload.get("advisory_summary"):
            return payload["advisory_summary"]
        try:
            from research_core.ecosystem_runtime.ecosystem_context import EcosystemContext

            return EcosystemContext.load(self._root).advisory_summary()
        except Exception:
            return {}

    def _load_macro_summary(self) -> dict[str, Any]:
        ssot = self._ssot()
        block = ssot.section("macro")
        if block:
            return block
        # LEGACY_RUNTIME_SOURCE
        payload, _ = _load_json(self._path("tae_macro_runtime.json"))
        if payload and payload.get("advisory_summary"):
            return payload["advisory_summary"]
        try:
            from research_core.macro_runtime.macro_context import MacroContext

            return MacroContext.load(self._root).advisory_summary()
        except Exception:
            return {}

    def _load_sector_summary(self) -> dict[str, Any]:
        ssot = self._ssot()
        block = ssot.section("sector")
        if block:
            return block
        # LEGACY_RUNTIME_SOURCE
        payload, _ = _load_json(self._path("tae_sector_runtime.json"))
        if payload and payload.get("advisory_summary"):
            return payload["advisory_summary"]
        try:
            from research_core.sector_runtime.sector_context import SectorContext

            return SectorContext.load(self._root).advisory_summary()
        except Exception:
            return {}

    def _load_confidence_summary(self) -> dict[str, Any]:
        ssot = self._ssot()
        block = ssot.section("confidence")
        if block:
            return block
        # LEGACY_RUNTIME_SOURCE
        payload, _ = _load_json(self._path("tae_confidence_runtime.json"))
        if payload and payload.get("advisory_summary"):
            return payload["advisory_summary"]
        try:
            from research_core.confidence_runtime.confidence_context import ConfidenceContext

            return ConfidenceContext.load(self._root).advisory_summary()
        except Exception:
            return {}

    @staticmethod
    def _dominant_verdict(index: dict[str, Any] | None) -> str | None:
        if not index:
            return None
        distribution = index.get("verdict_status_distribution") or {}
        if not distribution:
            return None
        return max(distribution.items(), key=lambda item: (item[1], item[0]))[0]

    @staticmethod
    def _warning_count(index: dict[str, Any] | None, relevant: dict[str, Any]) -> int:
        total = 0
        if index:
            dist = index.get("warnings_distribution") or {}
            total += sum(int(v) for v in dist.values())
            total += int(index.get("invalid_reports") or 0)
        for meta in relevant.values():
            total += len(meta.get("warnings") or [])
        return total

    def _analyze_warnings(
        self,
        index: dict[str, Any] | None,
        relevant: dict[str, Any],
        *,
        markets_open: bool | None,
        runtime: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        seen: set[str] = set()
        audit: list[dict[str, Any]] = []
        runtime = runtime or {}

        def _add(source: str, text: str) -> None:
            normalized = str(text).strip()
            if not normalized:
                return
            key = normalized.lower()
            if key in seen:
                return
            seen.add(key)
            classification = _classify_warning(
                normalized, markets_open=markets_open, runtime=runtime
            )
            audit.append(
                {
                    "source": source,
                    "text": normalized,
                    "classification": classification,
                }
            )

        if index:
            for text, count in (index.get("warnings_distribution") or {}).items():
                for _ in range(max(0, int(count))):
                    _add("tae_advisory_index.json", str(text))

        for name, meta in relevant.items():
            for warning in meta.get("warnings") or []:
                _add(name, str(warning))

        blocking = [
            item["text"]
            for item in audit
            if item["classification"] in BLOCKING_WARNING_CLASSES
        ]
        informational = [
            item["text"]
            for item in audit
            if item["classification"] in INFORMATIONAL_WARNING_CLASSES
            and item["classification"] != WARNING_CLASS_STALE_FALSE_POSITIVE
        ]
        stale_false_positive = [
            item["text"]
            for item in audit
            if item["classification"] == WARNING_CLASS_STALE_FALSE_POSITIVE
        ]

        return {
            "warning_audit": audit,
            "blocking_warnings": blocking,
            "informational_warnings": informational,
            "stale_false_positive_warnings": stale_false_positive,
            "blocking_warnings_count": len(blocking),
            "informational_warnings_count": len(informational),
            "stale_false_positive_warnings_count": len(stale_false_positive),
            "warning_count_total": len(audit),
        }

    @staticmethod
    def _historical_median_metrics(
        historical: dict[str, Any] | None,
    ) -> tuple[float | None, float | None, float | None, list[str]]:
        """Median-first view of historical results (robust shortlist)."""
        notes: list[str] = []
        if not historical:
            return None, None, None, ["tae_historical_results_analysis.json missing"]

        shortlist = historical.get("robust_strategy_shortlist") or []
        if not isinstance(shortlist, list) or not shortlist:
            return None, None, None, ["historical robust shortlist empty"]

        profit_values = [
            v
            for item in shortlist
            if isinstance(item, dict)
            for v in [_parse_float(item.get("avg_profit_pct"))]
            if v is not None
        ]
        sharpe_values = [
            v
            for item in shortlist
            if isinstance(item, dict)
            for v in [_parse_float(item.get("avg_sharpe"))]
            if v is not None
        ]

        median_profit = _median(profit_values)
        median_sharpe = _median(sharpe_values)

        mean_profit = None
        for line in historical.get("research_conclusions") or []:
            text = str(line)
            if "profit_pct" in text and "averages" in text.lower():
                parts = text.replace(",", "").split()
                for token in parts:
                    try:
                        mean_profit = float(token)
                    except ValueError:
                        continue
                break

        if (
            mean_profit is not None
            and median_profit is not None
            and abs(mean_profit) > max(10.0, abs(median_profit) * 10)
        ):
            notes.append(
                "Historical mean profit_pct is outlier-driven vs robust median "
                f"(mean≈{mean_profit:.2f}, median≈{median_profit:.2f})"
            )

        return median_profit, median_sharpe, mean_profit, notes

    def _derive_advisory(
        self,
        *,
        index: dict[str, Any] | None,
        index_error: str | None,
        runtime: dict[str, Any],
        relevant: dict[str, Any],
        reports_raw: dict[str, dict[str, Any] | None],
        warning_analysis: dict[str, Any],
    ) -> tuple[str, int, list[str], list[str]]:
        reasons: list[str] = []
        blockers: list[str] = []
        confidence = 55

        blocking_warnings = list(warning_analysis.get("blocking_warnings") or [])
        informational_warnings = list(warning_analysis.get("informational_warnings") or [])
        stale_false_positive_warnings = list(
            warning_analysis.get("stale_false_positive_warnings") or []
        )
        blocking_warning_count = int(warning_analysis.get("blocking_warnings_count") or 0)
        warning_count_total = int(warning_analysis.get("warning_count_total") or 0)

        if index_error or index is None:
            blockers.append("tae_advisory_index.json missing or invalid")
        else:
            total = int(index.get("total_reports") or 0)
            valid = int(index.get("valid_reports") or 0)
            invalid = int(index.get("invalid_reports") or 0)
            if total == 0:
                blockers.append("advisory index reports zero total_reports")
            if invalid > 0:
                blockers.append(f"{invalid} invalid TAE JSON report(s) in advisory index")
                confidence -= 20
            elif valid == total and total > 0:
                reasons.append(f"All {valid} indexed TAE reports parse as valid JSON")
                confidence += 10

        if warning_count_total:
            reasons.append(
                f"Aggregated TAE/live warnings: total={warning_count_total}, "
                f"blocking={blocking_warning_count}, informational={len(informational_warnings)}, "
                f"stale_false_positive={len(stale_false_positive_warnings)}"
            )
            confidence -= min(25, blocking_warning_count * 4)

        for stale in stale_false_positive_warnings[:8]:
            reasons.append(f"[STALE_FALSE_POSITIVE] {stale}")

        for info in informational_warnings[:8]:
            reasons.append(f"[INFO] {info}")

        historical = reports_raw.get("tae_historical_results_analysis.json")
        median_profit, median_sharpe, _mean_profit, hist_notes = (
            self._historical_median_metrics(historical)
        )
        for note in hist_notes:
            if "missing" in note or "empty" in note:
                blockers.append(note)
            else:
                reasons.append(note)

        meta = reports_raw.get("tae_meta_intelligence.json")
        meta_confidence = None
        if meta:
            obs = meta.get("strategic_observations") or {}
            conf = obs.get("overall_ecosystem_confidence") or {}
            meta_confidence = str(conf.get("confidence_label") or "").upper()
            composite = _parse_float(conf.get("composite_score"))
            if meta_confidence == "HIGH" and composite is not None and composite >= 0.85:
                reasons.append(f"Meta intelligence confidence HIGH ({composite:.3f})")
                confidence += 8
            elif meta_confidence:
                reasons.append(f"Meta intelligence confidence label: {meta_confidence}")
        else:
            blockers.append("tae_meta_intelligence.json missing")

        quick = reports_raw.get("tae_quick_health_check.json")
        quick_verdict = _extract_verdict(quick) if quick else None
        if quick_verdict in QUICK_HEALTH_READY:
            reasons.append(f"Quick health verdict: {quick_verdict}")
            confidence += 5
        elif quick is None:
            blockers.append("tae_quick_health_check.json missing")
        else:
            blockers.append(f"Quick health not ready: {quick_verdict or 'unknown'}")
            confidence -= 10

        dominant = self._dominant_verdict(index)
        if dominant:
            reasons.append(f"Dominant indexed verdict/status: {dominant}")
            if any(marker in dominant.upper() for marker in NEGATIVE_VERDICT_MARKERS):
                blockers.append(f"Dominant status negative: {dominant}")
                confidence -= 8

        open_positions = runtime.get("open_positions_count")
        if open_positions is None:
            blockers.append("open_positions_count unavailable")
        else:
            reasons.append(f"Open positions: {open_positions}")
            if open_positions >= LIVE_MAX_POSITIONS:
                blockers.append(f"Open positions at live max ({LIVE_MAX_POSITIONS})")
                confidence -= 12

        bot_status = str(
            runtime.get("bot_status_effective") or runtime.get("bot_status") or "UNKNOWN"
        ).upper()
        markets_open = runtime.get("any_market_open")
        if markets_open is False and bot_status == "STOPPED":
            reasons.append("Bot status: STOPPED (expected — all markets closed)")
        else:
            reasons.append(f"Bot status: {bot_status}")
            if runtime.get("bot_status_effective") and runtime.get("bot_status_effective") != runtime.get("bot_status"):
                reasons.append(
                    f"Bot runtime evidence: effective={runtime.get('bot_status_effective')} "
                    f"(file={runtime.get('bot_status')}, pgrep={runtime.get('bot_process_pgrep_pids')})"
                )
            if markets_open and bot_status != "RUNNING":
                blockers.append("Bot not RUNNING while market session open")
                confidence -= 8

        strong_buys = int(runtime.get("high_score_strong_buy_count") or 0)
        take_profit = int(runtime.get("take_profit_signal_count") or 0)
        losing_open = int(runtime.get("losing_open_positions") or 0)
        signals_present = bool(runtime.get("live_signals_present"))

        if signals_present:
            reasons.append(
                f"Live signals: {runtime.get('latest_live_signal_count')} rows, "
                f"{strong_buys} STRONG BUY (>={LIVE_MIN_BUY_SCORE})"
            )
        else:
            blockers.append("live_signals.csv missing")

        if median_profit is not None:
            reasons.append(f"Historical robust median avg_profit_pct: {median_profit:.2f}")
        if median_sharpe is not None:
            reasons.append(f"Historical robust median avg_sharpe: {median_sharpe:.2f}")

        for item in runtime.get("strong_buy_historical_summary") or []:
            ticker = item.get("ticker")
            edge = item.get("edge")
            wr = item.get("win_rate")
            sr = item.get("sharpe")
            reasons.append(
                f"[HISTORICAL_CONTEXT] {ticker}: edge={edge} win_rate={wr} "
                f"hist_sharpe={sr} committee={item.get('committee_score')}"
            )

        if runtime.get("historical_enrichment_present"):
            reasons.append(
                f"Live signals historical enrichment active "
                f"({runtime.get('historical_enriched_strong_buy_count', 0)} STRONG BUY rows)"
            )

        research_summary = self._load_research_advisory_summary()
        if research_summary:
            reasons.append("[RESEARCH_CONTEXT] Top Research Candidates")
            for cand in research_summary.get("top_research_candidates") or []:
                reasons.append(
                    f"[RESEARCH_CONTEXT] candidate {cand.get('ticker')}: "
                    f"momentum={cand.get('momentum_score')} edge={cand.get('edge')}"
                )
            reasons.append(
                f"[RESEARCH_CONTEXT] Momentum Summary: {research_summary.get('momentum_summary')}"
            )
            reasons.append(
                f"[RESEARCH_CONTEXT] Sector Summary: {research_summary.get('sector_summary')}"
            )
            reasons.append(
                f"[RESEARCH_CONTEXT] Regional Summary: {research_summary.get('regional_summary')}"
            )
            reasons.append(
                f"[RESEARCH_CONTEXT] Macro Summary: {research_summary.get('macro_summary')}"
            )
            reasons.append(
                f"[RESEARCH_CONTEXT] Counterfactual Summary: "
                f"{research_summary.get('counterfactual_summary')}"
            )

        for item in runtime.get("strong_buy_research_summary") or []:
            reasons.append(
                f"[RESEARCH_CONTEXT] {item.get('ticker')}: momentum={item.get('momentum')} "
                f"sector={item.get('sector')} regional={item.get('regional')} "
                f"confidence={item.get('confidence')}"
            )

        if runtime.get("research_enrichment_present"):
            reasons.append(
                f"Live signals research enrichment active "
                f"({runtime.get('research_enriched_strong_buy_count', 0)} STRONG BUY rows)"
            )

        committee_summary = self._load_committee_advisory_summary()
        if committee_summary:
            reasons.append(f"[COMMITTEE_CONTEXT] Committee Summary: {committee_summary.get('committee_summary')}")
            reasons.append(
                f"[COMMITTEE_CONTEXT] Committee Consensus: {committee_summary.get('committee_consensus')}"
            )
            reasons.append(
                f"[COMMITTEE_CONTEXT] Committee Confidence: {committee_summary.get('committee_confidence')}"
            )
            weighted = committee_summary.get("weighted_decisions") or {}
            reasons.append(
                f"[COMMITTEE_CONTEXT] Weighted Decisions: "
                f"decision={weighted.get('final_decision')} score={weighted.get('weighted_score')}"
            )
            for cand in committee_summary.get("highest_confidence_candidates") or []:
                reasons.append(
                    f"[COMMITTEE_CONTEXT] Top candidate {cand.get('ticker')}: "
                    f"confidence={cand.get('confidence')} decision={cand.get('decision')}"
                )

        for item in runtime.get("strong_buy_committee_summary") or []:
            reasons.append(
                f"[COMMITTEE_CONTEXT] {item.get('ticker')}: decision={item.get('decision')} "
                f"confidence={item.get('confidence')} weighted={item.get('weighted_score')}"
            )

        if runtime.get("committee_enrichment_present"):
            reasons.append(
                f"Live signals committee enrichment active "
                f"({runtime.get('committee_enriched_strong_buy_count', 0)} STRONG BUY rows)"
            )

        allocation_summary = self._load_allocation_advisory_summary()
        if allocation_summary:
            reasons.append(
                f"[ALLOCATION_CONTEXT] Regional Allocation: {allocation_summary.get('regional_allocation')}"
            )
            sector = allocation_summary.get("sector_allocation") or {}
            reasons.append(
                f"[ALLOCATION_CONTEXT] Sector Allocation: leader={sector.get('leader')} "
                f"score={sector.get('score')}"
            )
            macro = allocation_summary.get("macro_allocation") or {}
            reasons.append(
                f"[ALLOCATION_CONTEXT] Macro Allocation: verdict={macro.get('verdict')} "
                f"adaptive={macro.get('adaptive')}"
            )
            reasons.append(
                f"[ALLOCATION_CONTEXT] Capital Flow: {allocation_summary.get('capital_flow')}"
            )
            reasons.append(
                f"[ALLOCATION_CONTEXT] Strategic Bias: {allocation_summary.get('strategic_bias')}"
            )
            reasons.append(
                f"[ALLOCATION_CONTEXT] Allocation Confidence: "
                f"{allocation_summary.get('allocation_confidence')}"
            )

        for item in runtime.get("strong_buy_allocation_summary") or []:
            reasons.append(
                f"[ALLOCATION_CONTEXT] {item.get('ticker')}: score={item.get('allocation_score')} "
                f"region={item.get('region')} capital_flow={item.get('capital_flow')}"
            )

        if runtime.get("allocation_enrichment_present"):
            reasons.append(
                f"Live signals allocation enrichment active "
                f"({runtime.get('allocation_enriched_strong_buy_count', 0)} STRONG BUY rows)"
            )

        meta_summary = self._load_meta_advisory_summary()
        if meta_summary:
            reasons.append(f"[META_CONTEXT] Meta Summary: {meta_summary.get('meta_summary')}")
            reasons.append(
                f"[META_CONTEXT] Meta Confidence: {meta_summary.get('meta_confidence')}"
            )
            reasons.append(
                f"[META_CONTEXT] Ecosystem Health: {meta_summary.get('ecosystem_health')}"
            )
            unified = meta_summary.get("unified_runtime_score_summary") or {}
            reasons.append(
                f"[META_CONTEXT] Unified Runtime Score Summary: "
                f"avg={unified.get('avg')} max={unified.get('max')} count={unified.get('count')}"
            )
            for cand in meta_summary.get("top_unified_candidates") or []:
                reasons.append(
                    f"[META_CONTEXT] Unified candidate {cand.get('ticker')}: "
                    f"score={cand.get('unified_runtime_score')} meta={cand.get('meta_score')}"
                )

        for item in runtime.get("strong_buy_meta_summary") or []:
            reasons.append(
                f"[META_CONTEXT] {item.get('ticker')}: meta_score={item.get('meta_score')} "
                f"unified={item.get('unified_runtime_score')} health={item.get('meta_health')}"
            )

        if runtime.get("meta_enrichment_present"):
            reasons.append(
                f"Live signals meta enrichment active "
                f"({runtime.get('meta_enriched_strong_buy_count', 0)} STRONG BUY rows)"
            )

        unified_summary = self._load_unified_runtime_summary()
        if unified_summary:
            score_summary = unified_summary.get("unified_runtime_score_summary") or {}
            conf_summary = unified_summary.get("confidence_summary") or {}
            reasons.append(
                f"[UNIFIED_RUNTIME] SSOT records: {unified_summary.get('record_count')}"
            )
            reasons.append(
                f"[UNIFIED_RUNTIME] Top Scores Summary: "
                f"avg={score_summary.get('avg')} max={score_summary.get('max')} "
                f"count={score_summary.get('count')}"
            )
            reasons.append(
                f"[UNIFIED_RUNTIME] Confidence Summary: "
                f"avg={conf_summary.get('avg')} max={conf_summary.get('max')}"
            )
            top_candidates = unified_summary.get("top_candidates") or []
            if top_candidates:
                reasons.append(
                    f"[UNIFIED_RUNTIME] Top Candidates: {', '.join(str(t) for t in top_candidates[:10])}"
                )
            for cand in unified_summary.get("top_unified_candidates") or []:
                reasons.append(
                    f"[UNIFIED_RUNTIME] {cand.get('ticker')}: "
                    f"score={cand.get('unified_runtime_score')} "
                    f"confidence={cand.get('unified_runtime_confidence')} "
                    f"recommendation={cand.get('unified_runtime_recommendation')}"
                )

        strategy_summary = self._load_strategy_advisory_summary()
        if strategy_summary:
            reasons.append(
                f"[STRATEGY_CONTEXT] Discovery confidence avg: "
                f"{strategy_summary.get('discovery_avg_confidence')}"
            )
            reasons.append(
                f"[STRATEGY_CONTEXT] Simulation confidence: "
                f"{strategy_summary.get('simulation_confidence')}"
            )
            for item in strategy_summary.get("top_discovered_strategies") or []:
                reasons.append(
                    f"[STRATEGY_CONTEXT] Discovered {item.get('discovery_id')}: "
                    f"market={item.get('market')} confidence={item.get('confidence_seed')}"
                )
            for item in strategy_summary.get("top_simulated_strategies") or []:
                reasons.append(
                    f"[STRATEGY_CONTEXT] Simulated {item.get('strategy_id')}: "
                    f"market={item.get('market')} return={item.get('profit_pct')} "
                    f"edge={item.get('expectancy')} drawdown={item.get('max_drawdown')} "
                    f"confidence={strategy_summary.get('simulation_confidence')}"
                )

        event_summary = self._load_event_memory_summary()
        if event_summary:
            reasons.append(
                f"[EVENT_MEMORY_CONTEXT] Verdict: {event_summary.get('event_memory_verdict') or event_summary.get('verdict')}"
            )
            reasons.append(
                f"[EVENT_MEMORY_CONTEXT] Events: {event_summary.get('event_count')} "
                f"schema={event_summary.get('schema_validation_passed')}"
            )

        cf_summary = self._load_counterfactual_summary()
        if cf_summary:
            reasons.append(
                f"[COUNTERFACTUAL_CONTEXT] Entry: {cf_summary.get('entry_verdict')} "
                f"Exit: {cf_summary.get('exit_verdict')}"
            )
            reasons.append(
                f"[COUNTERFACTUAL_CONTEXT] Best scenario: {cf_summary.get('best_scenario_id')} "
                f"alt_return={cf_summary.get('expected_alternative_return')}"
            )
            reasons.append(
                f"[COUNTERFACTUAL_CONTEXT] Shadow events: {cf_summary.get('shadow_total_events')} "
                f"block_rate={cf_summary.get('shadow_block_rate')} "
                f"outcome={cf_summary.get('outcome_memory')}"
            )
            for ticker in cf_summary.get("top_entry_tickers") or []:
                reasons.append(f"[COUNTERFACTUAL_CONTEXT] Entry ticker: {ticker}")
            for ticker in cf_summary.get("top_exit_tickers") or []:
                reasons.append(f"[COUNTERFACTUAL_CONTEXT] Exit ticker: {ticker}")

        eco_summary = self._load_ecosystem_summary()
        if eco_summary:
            reasons.append(
                f"[ECOSYSTEM_CONTEXT] Run: {eco_summary.get('ecosystem_run_status')} "
                f"Orchestrator: {eco_summary.get('orchestrator_status')}"
            )
            reasons.append(
                f"[EVIDENCE_CONTEXT] Verdict: {eco_summary.get('evidence_verdict')} "
                f"Gate: {eco_summary.get('evidence_gate')} "
                f"score={eco_summary.get('evidence_score')} "
                f"allowed={eco_summary.get('evidence_allowed_count')}"
            )
            for item in eco_summary.get("top_evidence_candidates") or []:
                reasons.append(
                    f"[EVIDENCE_CONTEXT] Candidate: {item.get('evidence_id')} "
                    f"gate={item.get('gate_status')}"
                )
            reasons.append(
                f"[DAILY_INTELLIGENCE_CONTEXT] Score: {eco_summary.get('daily_intelligence_score')} "
                f"health={eco_summary.get('daily_ecosystem_health')} "
                f"legacy_runner={eco_summary.get('legacy_daily_runner_present')}"
            )
            for item in eco_summary.get("top_daily_intelligence_candidates") or []:
                reasons.append(
                    f"[DAILY_INTELLIGENCE_CONTEXT] Priority: {item.get('title')} "
                    f"score={item.get('priority_score')}"
                )

        macro_summary = self._load_macro_summary()
        if macro_summary:
            reasons.append(
                f"[MACRO_CONTEXT] Verdict: {macro_summary.get('macro_verdict')} "
                f"Regime: {macro_summary.get('macro_regime')} "
                f"score={macro_summary.get('macro_score')}"
            )
            reasons.append(
                f"[MACRO_CONTEXT] Rates: {macro_summary.get('interest_rate_context')} "
                f"Inflation: {macro_summary.get('inflation_context')}"
            )

        sector_summary = self._load_sector_summary()
        if sector_summary:
            reasons.append(
                f"[SECTOR_CONTEXT] Top: {sector_summary.get('top_sector')} "
                f"score={sector_summary.get('sector_score')} "
                f"history={sector_summary.get('history_rows')}"
            )
            for item in sector_summary.get("top_sectors") or []:
                reasons.append(
                    f"[SECTOR_CONTEXT] Sector: {item.get('sector')} score={item.get('score')}"
                )

        conf_summary = self._load_confidence_summary()
        if conf_summary:
            reasons.append(
                f"[CONFIDENCE_CONTEXT] Validation: {conf_summary.get('validation_status')} "
                f"score={conf_summary.get('confidence_score')} "
                f"vote_accuracy={conf_summary.get('vote_accuracy_avg')}"
            )
            reasons.append(
                f"[CONFIDENCE_CONTEXT] Rules: {conf_summary.get('validation_rules_count')} "
                f"adaptive_weight={conf_summary.get('adaptive_weight_avg')}"
            )
            for item in conf_summary.get("top_vote_accuracy") or []:
                reasons.append(
                    f"[CONFIDENCE_CONTEXT] Vote: {item.get('vote')} "
                    f"accuracy={item.get('accuracy')} weight={item.get('weight')}"
                )

        confidence = max(0, min(100, confidence))

        # --- Action selection (conservative; RISK only on real blocking signals) ---
        invalid_reports = int((index or {}).get("invalid_reports") or 0)
        if invalid_reports > 0:
            return "RISK_ADVISORY", confidence, reasons, blockers

        trading_blockers = [
            b
            for b in blockers
            if b not in informational_warnings and "expected" not in b.lower()
        ]

        if blocking_warning_count >= 2:
            blockers.append(
                f"Elevated blocking warning count ({blocking_warning_count})"
            )
            for warning in blocking_warnings[:5]:
                blockers.append(f"Blocking warning: {warning}")
            return "RISK_ADVISORY", confidence, reasons, blockers

        if len(trading_blockers) >= 3:
            return "RISK_ADVISORY", confidence, reasons, blockers

        if losing_open >= 2 or any("outlier-driven" in r for r in reasons):
            if any("outlier-driven" in r for r in reasons):
                blockers.append("Historical mean/median profit contradiction (outlier-driven)")
            if losing_open >= 2:
                blockers.append(f"{losing_open} open positions below -3% PnL")
            return "RISK_ADVISORY", confidence, reasons, blockers

        if quick_verdict and quick_verdict not in QUICK_HEALTH_READY:
            blockers.append(f"Quick health not ready: {quick_verdict}")
            return "RISK_ADVISORY", confidence, reasons, blockers

        perf = reports_raw.get("tae_strategic_performance_audit.json")
        if perf:
            perf_verdict = str(_extract_verdict(perf) or "").upper()
            if any(m in perf_verdict for m in ("ANOMALY", "MISMATCH", "DISTORTION")):
                blockers.append(f"Strategic performance audit flag: {perf_verdict}")
                return "RISK_ADVISORY", confidence, reasons, blockers

        if take_profit > 0 or losing_open >= 1:
            if take_profit > 0:
                reasons.append(f"{take_profit} TAKE PROFIT live signal(s) — advisory exit review")
            if losing_open >= 1:
                reasons.append(
                    f"{losing_open} open position(s) at or below -3% PnL — advisory risk review"
                )
            return "SELL_ADVISORY", confidence, reasons, blockers

        buy_allowed = (
            invalid_reports == 0
            and not blockers
            and signals_present
            and strong_buys >= 1
            and open_positions is not None
            and open_positions < LIVE_MAX_POSITIONS
            and quick_verdict in QUICK_HEALTH_READY
            and meta_confidence == "HIGH"
            and median_sharpe is not None
            and median_sharpe >= 0.5
            and blocking_warning_count == 0
        )

        if buy_allowed:
            reasons.append(
                "Aligned live STRONG BUY signals, HIGH meta confidence, valid TAE index, "
                "and median-first historical Sharpe support — advisory only"
            )
            confidence = min(100, confidence + 5)
            return "BUY_ADVISORY", confidence, reasons, blockers

        if blockers:
            reasons.append("Incomplete or blocked inputs — defaulting to NO_ACTION")

        return "NO_ACTION", confidence, reasons, blockers

    def build(self, *, live_bot_mtime_before: float | None = None) -> LiveAdvisoryReport:
        index, index_error = self._load_advisory_index()
        portfolio_part, portfolio_blockers = self._portfolio_snapshot()
        signals_part, signal_blockers = self._live_signals_snapshot()
        relevant_meta = self._load_relevant_reports()

        reports_raw: dict[str, dict[str, Any] | None] = {}
        for name in RELEVANT_TAE_REPORTS:
            payload, _err = _load_json(self._path(name))
            reports_raw[name] = payload

        markets_open: bool | None = None
        market_statuses: dict[str, Any] = {}
        try:
            from markets.market_hours import any_market_open, get_market_statuses

            market_statuses = get_market_statuses()
            markets_open = any_market_open()
        except Exception:
            market_statuses = {}

        process_evidence, runtime_evidence_used = _probe_runtime_processes(self._root)

        runtime_snapshot = {
            **portfolio_part,
            **signals_part,
            **process_evidence,
            "bot_status": self._bot_status(),
            "any_market_open": markets_open,
            "market_statuses": market_statuses,
        }
        if process_evidence.get("bot_status_effective"):
            runtime_snapshot["bot_status_effective"] = process_evidence["bot_status_effective"]

        warning_analysis = self._analyze_warnings(
            index,
            relevant_meta,
            markets_open=markets_open,
            runtime=runtime_snapshot,
        )
        warning_count = int(warning_analysis.get("warning_count_total") or 0)
        tae_snapshot = {
            "total_reports": int((index or {}).get("total_reports") or 0),
            "valid_reports": int((index or {}).get("valid_reports") or 0),
            "invalid_reports": int((index or {}).get("invalid_reports") or 0),
            "warning_count": warning_count,
            "blocking_warnings_count": warning_analysis.get("blocking_warnings_count", 0),
            "informational_warnings_count": warning_analysis.get(
                "informational_warnings_count", 0
            ),
            "stale_false_positive_warnings_count": warning_analysis.get(
                "stale_false_positive_warnings_count", 0
            ),
            "dominant_status": self._dominant_verdict(index),
            "advisory_index_present": index is not None and index_error is None,
            "advisory_index_generated_at": (index or {}).get("generated_at"),
            "relevant_reports_loaded": [
                name for name, meta in relevant_meta.items() if meta.get("state") == "ok"
            ],
        }

        all_blockers = list(portfolio_blockers) + list(signal_blockers)
        action, confidence, reasons, blockers = self._derive_advisory(
            index=index,
            index_error=index_error,
            runtime=runtime_snapshot,
            relevant=relevant_meta,
            reports_raw=reports_raw,
            warning_analysis=warning_analysis,
        )
        blockers = all_blockers + blockers

        live_bot_not_modified = True
        if live_bot_mtime_before is not None and self._path(LIVE_BOT_PATH).is_file():
            live_bot_not_modified = (
                self._path(LIVE_BOT_PATH).stat().st_mtime == live_bot_mtime_before
            )

        return LiveAdvisoryReport(
            runtime_snapshot=runtime_snapshot,
            tae_snapshot=tae_snapshot,
            action=action,
            confidence=confidence,
            reasons=reasons,
            blockers=blockers,
            blocking_warnings=list(warning_analysis.get("blocking_warnings") or []),
            informational_warnings=list(warning_analysis.get("informational_warnings") or []),
            stale_false_positive_warnings=list(
                warning_analysis.get("stale_false_positive_warnings") or []
            ),
            warning_audit=list(warning_analysis.get("warning_audit") or []),
            runtime_evidence_used=runtime_evidence_used,
            relevant_reports={
                name: {
                    "state": meta.get("state"),
                    "verdict": meta.get("verdict"),
                    "warning_count": len(meta.get("warnings") or []),
                }
                for name, meta in relevant_meta.items()
            },
            live_bot_not_modified=live_bot_not_modified,
        )

    def build_and_persist(
        self,
        output_path: Path | None = None,
        *,
        live_bot_mtime_before: float | None = None,
    ) -> tuple[LiveAdvisoryReport, Path]:
        report = self.build(live_bot_mtime_before=live_bot_mtime_before)
        path = output_path or self._path(DEFAULT_OUTPUT_PATH)
        path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return report, path

    @staticmethod
    def format_text(report: LiveAdvisoryReport) -> str:
        payload = report.to_dict()
        lines = [
            "===== TAE LIVE ADVISORY BRIDGE — SPRINT X.7C =====",
            "",
            f"Mode: {payload['mode']}",
            f"Live trading impact: {payload['live_trading_impact']}",
            f"Generated: {payload['generated_at']}",
            "",
            "===== RUNTIME SNAPSHOT =====",
        ]
        for key, value in payload["runtime_snapshot"].items():
            lines.append(f"  {key}: {value}")
        lines.extend(["", "===== TAE SNAPSHOT ====="])
        for key, value in payload["tae_snapshot"].items():
            lines.append(f"  {key}: {value}")
        lines.extend(
            [
                "",
                "===== ADVISORY =====",
                f"  action: {payload['advisory']['action']}",
                f"  block_new_buy: {payload.get('block_new_buy')}",
                f"  confidence: {payload['advisory']['confidence']}",
                "",
                "  reasons:",
            ]
        )
        for reason in payload["advisory"]["reasons"]:
            lines.append(f"    • {reason}")
        lines.append("")
        lines.append("  blockers:")
        if payload["advisory"]["blockers"]:
            for blocker in payload["advisory"]["blockers"]:
                lines.append(f"    • {blocker}")
        else:
            lines.append("    • (none)")
        lines.extend(["", "  stale_false_positive_warnings:"])
        stale = payload["advisory"].get("stale_false_positive_warnings") or []
        if stale:
            for item in stale:
                lines.append(f"    • {item}")
        else:
            lines.append("    • (none)")
        lines.extend(["", "  runtime_evidence_used:"])
        evidence = payload.get("runtime_evidence_used") or []
        if evidence:
            for item in evidence:
                lines.append(f"    • {item}")
        else:
            lines.append("    • (none)")
        lines.extend(["", "===== SAFETY ====="])
        for key, value in payload["safety"].items():
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)
