#!/usr/bin/env python3
"""
TAE Sprint X.10B — Global Scanner → Runtime Candidate Queue

CONTROLLED INTEGRATION | NO_BROKER | NO_EXECUTION | NO_STRATEGY_CHANGE
Does NOT modify live_bot.py, watchlist.txt, or call buy_position().
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAFETY_BANNER = (
    "CONTROLLED_INTEGRATION | NO_BROKER | NO_EXECUTION | NO_STRATEGY_CHANGE | "
    "NO_WATCHLIST_WRITE | NO_BUY_SELL_LOGIC"
)

DEFAULT_ROOT = Path(".")
WATCHLIST_FILE = "watchlist.txt"
PORTFOLIO_FILE = "portfolio.csv"
ADVISORY_FILE = "tae_live_advisory.json"

OUTPUT_JSON = "tae_candidate_queue.json"
OUTPUT_MD = "tae_candidate_queue.md"
OUTPUT_CSV = "tae_candidate_queue.csv"

CSV_STALE_MAX_AGE_HOURS = 168.0
MIN_RANK_SCORE = 40.0
MIN_MONITOR_RANK_SCORE = 25.0
MAX_PROMOTION_ELIGIBLE = 10
MAX_MONITOR = 25

TICKER_SOURCES: tuple[tuple[str, int, str], ...] = (
    ("global_opportunity_ranking.csv", 1, "global_ranking"),
    ("global_candidates.csv", 2, "global_candidates"),
    ("multi_market_candidates.csv", 3, "multi_market_scanner"),
    ("watchlist_candidates.csv", 4, "us_market_scanner"),
)

CLASSIFICATIONS = (
    "NEW_CANDIDATE",
    "ALREADY_IN_WATCHLIST",
    "ALREADY_HELD",
    "MARKET_CLOSED",
    "LOW_RANK",
    "STALE_SOURCE",
    "PROMOTION_ELIGIBLE",
    "MONITOR_ONLY",
)

RECOMMENDED_ACTIONS = (
    "PROMOTE_MAX_10",
    "WAIT_FOR_MARKET_OPEN",
    "REFRESH_SCANNER",
    "NO_ACTION",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().upper() in {"1", "TRUE", "YES", "ON"}


def _file_age_hours(path: Path) -> float | None:
    if not path.is_file():
        return None
    mtime = path.stat().st_mtime
    return (datetime.now(timezone.utc).timestamp() - mtime) / 3600.0


def _artifact_status(path: Path) -> str:
    if not path.is_file():
        return "NO_DATA"
    age = _file_age_hours(path)
    if age is None:
        return "NO_DATA"
    return "STALE" if age > CSV_STALE_MAX_AGE_HOURS else "OK"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _infer_market(ticker: str, row_market: str | None = None) -> str:
    if row_market:
        market = str(row_market).strip().upper()
        if market in {"US", "EU", "UK", "ASIA"}:
            return market
    try:
        from markets.market_hours import get_ticker_market

        return get_ticker_market(ticker)
    except Exception:
        ticker = ticker.upper()
        if ticker.endswith(".L"):
            return "UK"
        if ticker.endswith((".DE", ".PA", ".AS", ".MI", ".SW", ".MC", ".BR")):
            return "EU"
        if ticker.endswith((".HK", ".T", ".KS", ".SI")):
            return "ASIA"
        return "US"


def _read_watchlist(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [
        line.strip().upper()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _read_open_positions(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    holdings: dict[str, float] = {}
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            for row in csv.DictReader(handle):
                ticker = str(row.get("Ticker") or "").strip().upper()
                if not ticker:
                    continue
                action = str(row.get("Action") or "").strip().upper()
                shares = _parse_float(row.get("Shares")) or 0.0
                if action == "BUY":
                    holdings[ticker] = holdings.get(ticker, 0.0) + shares
                elif action == "SELL":
                    holdings[ticker] = holdings.get(ticker, 0.0) - shares
    except OSError:
        return set()
    return {ticker for ticker, shares in holdings.items() if shares > 1e-6}


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


def _market_open_now(ticker: str, row_market_open: bool | None) -> bool:
    if row_market_open is not None:
        return row_market_open
    try:
        from markets.market_hours import is_ticker_market_open

        return is_ticker_market_open(ticker)
    except Exception:
        return False


def _market_statuses() -> dict[str, bool]:
    try:
        from markets.market_hours import get_market_statuses

        return get_market_statuses()
    except Exception:
        return {}


@dataclass
class QueueCandidate:
    ticker: str
    market: str
    rank_score: float
    source: str
    source_priority: int = 99
    sources_all: list[str] = field(default_factory=list)
    source_status: str = "NO_DATA"
    scanner_score: float | None = None
    global_rank_score: float | None = None
    signal: str | None = None
    price: float | None = None
    already_held: bool = False
    already_in_watchlist: bool = False
    market_open: bool = False
    promotion_eligible: bool = False
    classification: str = "NEW_CANDIDATE"
    reason: str = ""
    priority: int = 0
    committee_decision: str | None = None
    committee_confidence: float | None = None
    committee_weighted_score: float | None = None
    committee_bonus: float = 0.0
    historical_bonus: float = 0.0
    research_bonus: float = 0.0
    learning_bonus: float = 0.0
    allocation_bonus: float = 0.0
    allocation_score: float | None = None
    allocation_confidence: float | None = None
    meta_bonus: float = 0.0
    meta_score: float | None = None
    meta_confidence: float | None = None
    strategy_discovery_bonus: float = 0.0
    strategy_simulation_bonus: float = 0.0
    event_memory_bonus: float = 0.0
    counterfactual_bonus: float = 0.0
    entry_bonus: float = 0.0
    exit_bonus: float = 0.0
    shadow_bonus: float = 0.0
    unified_runtime_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "market": self.market,
            "rank_score": round(self.rank_score, 4),
            "source": self.source,
            "source_priority": self.source_priority,
            "sources_all": list(self.sources_all),
            "source_status": self.source_status,
            "scanner_score": self.scanner_score,
            "global_rank_score": self.global_rank_score,
            "signal": self.signal,
            "price": self.price,
            "already_held": self.already_held,
            "already_in_watchlist": self.already_in_watchlist,
            "market_open": self.market_open,
            "promotion_eligible": self.promotion_eligible,
            "classification": self.classification,
            "reason": self.reason,
            "priority": self.priority,
            "committee_decision": self.committee_decision,
            "committee_confidence": self.committee_confidence,
            "committee_weighted_score": self.committee_weighted_score,
            "committee_bonus": round(self.committee_bonus, 4),
            "historical_bonus": round(self.historical_bonus, 4),
            "research_bonus": round(self.research_bonus, 4),
            "learning_bonus": round(self.learning_bonus, 4),
            "allocation_bonus": round(self.allocation_bonus, 4),
            "allocation_score": self.allocation_score,
            "allocation_confidence": self.allocation_confidence,
            "meta_bonus": round(self.meta_bonus, 4),
            "meta_score": self.meta_score,
            "meta_confidence": self.meta_confidence,
            "strategy_discovery_bonus": round(self.strategy_discovery_bonus, 4),
            "strategy_simulation_bonus": round(self.strategy_simulation_bonus, 4),
            "event_memory_bonus": round(self.event_memory_bonus, 4),
            "counterfactual_bonus": round(self.counterfactual_bonus, 4),
            "entry_bonus": round(self.entry_bonus, 4),
            "exit_bonus": round(self.exit_bonus, 4),
            "shadow_bonus": round(self.shadow_bonus, 4),
            "unified_runtime_score": self.unified_runtime_score,
        }


class CandidateQueueBuilder:
    def __init__(self, root: Path | str = DEFAULT_ROOT) -> None:
        self.root = Path(root)
        self.sources_meta: dict[str, dict[str, Any]] = {}

    def _register_source(self, name: str, path: Path, row_count: int) -> str:
        status = _artifact_status(path)
        age = _file_age_hours(path)
        self.sources_meta[name] = {
            "path": str(path),
            "present": path.is_file(),
            "status": status,
            "age_hours": round(age, 2) if age is not None else None,
            "row_count": row_count,
        }
        return status

    def _score_from_row(self, row: dict[str, str], source_kind: str) -> float:
        if source_kind == "global_ranking":
            rank = _parse_float(row.get("Global_Rank_Score"))
            if rank is not None:
                return rank
        score = _parse_float(row.get("Score"))
        if score is not None:
            return score
        technical = _parse_float(row.get("Technical_Score"))
        return technical if technical is not None else 0.0

    def _merge_row(
        self,
        merged: dict[str, QueueCandidate],
        row: dict[str, str],
        *,
        artifact_name: str,
        priority: int,
        source_kind: str,
        source_status: str,
    ) -> None:
        ticker = str(row.get("Ticker") or "").strip().upper()
        if not ticker:
            return

        rank_score = self._score_from_row(row, source_kind)
        market = _infer_market(ticker, row.get("Market"))
        row_market_open = (
            _parse_bool(row.get("Market_Open")) if row.get("Market_Open") not in (None, "") else None
        )

        if ticker not in merged or priority < merged[ticker].source_priority:
            record = merged.get(ticker) or QueueCandidate(
                ticker=ticker,
                market=market,
                rank_score=rank_score,
                source=artifact_name,
            )
            record.market = market
            record.rank_score = rank_score
            record.source = artifact_name
            record.source_priority = priority
            record.source_status = source_status
            record.scanner_score = _parse_float(row.get("Score"))
            record.global_rank_score = _parse_float(row.get("Global_Rank_Score"))
            record.signal = str(row.get("Signal") or "").strip() or None
            record.price = _parse_float(row.get("Price"))
            record.market_open = _market_open_now(ticker, row_market_open)
            merged[ticker] = record
        else:
            record = merged[ticker]
            if record.scanner_score is None:
                record.scanner_score = _parse_float(row.get("Score"))
            if record.global_rank_score is None:
                record.global_rank_score = _parse_float(row.get("Global_Rank_Score"))
            if row_market_open is not None:
                record.market_open = row_market_open

        if artifact_name not in merged[ticker].sources_all:
            merged[ticker].sources_all.append(artifact_name)

    def _load_unified_runtime(self) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
        payload = _load_json(self.root / "tae_unified_runtime.json") or {}
        records = payload.get("records") or {}
        if not isinstance(records, dict):
            records = {}
        by_ticker = {
            str(k).upper(): v for k, v in records.items() if isinstance(v, dict)
        }
        if not by_ticker and payload.get("records_list"):
            by_ticker = {
                str(r.get("Ticker") or "").upper(): r
                for r in payload["records_list"]
                if isinstance(r, dict) and r.get("Ticker")
            }
        return by_ticker, payload.get("advisory_summary") or {}, payload

    def _apply_runtime_bonuses(
        self,
        merged: dict[str, QueueCandidate],
        unified_by_ticker: dict[str, dict[str, Any]],
    ) -> None:
        for record in merged.values():
            ctx = unified_by_ticker.get(record.ticker, {})

            record.committee_decision = str(ctx.get("Committee_Decision") or "") or None
            record.committee_confidence = _parse_float(ctx.get("Committee_Confidence"))
            record.committee_weighted_score = _parse_float(ctx.get("Committee_Weighted_Score"))
            record.allocation_score = _parse_float(ctx.get("Allocation_Score"))
            record.allocation_confidence = _parse_float(ctx.get("Allocation_Confidence"))
            record.meta_score = _parse_float(ctx.get("Meta_Score"))
            record.meta_confidence = _parse_float(ctx.get("Meta_Confidence"))
            record.unified_runtime_score = _parse_float(ctx.get("Unified_Runtime_Score"))
            record.strategy_discovery_bonus = round(_parse_float(ctx.get("strategy_discovery_bonus")) or 0.0, 4)
            record.strategy_simulation_bonus = round(_parse_float(ctx.get("strategy_simulation_bonus")) or 0.0, 4)
            record.event_memory_bonus = round(_parse_float(ctx.get("event_memory_bonus")) or 0.0, 4)
            record.counterfactual_bonus = round(_parse_float(ctx.get("counterfactual_bonus")) or 0.0, 4)
            record.entry_bonus = round(_parse_float(ctx.get("entry_bonus")) or 0.0, 4)
            record.exit_bonus = round(_parse_float(ctx.get("exit_bonus")) or 0.0, 4)
            record.shadow_bonus = round(_parse_float(ctx.get("shadow_bonus")) or 0.0, 4)

            record.historical_bonus = round(_parse_float(ctx.get("historical_bonus")) or 0.0, 4)
            record.research_bonus = round(_parse_float(ctx.get("research_bonus")) or 0.0, 4)
            record.committee_bonus = round(_parse_float(ctx.get("committee_bonus")) or 0.0, 4)
            record.learning_bonus = round(_parse_float(ctx.get("learning_bonus")) or 0.0, 4)
            record.allocation_bonus = round(_parse_float(ctx.get("allocation_bonus")) or 0.0, 4)
            record.meta_bonus = round(_parse_float(ctx.get("meta_bonus")) or 0.0, 4)

            if ctx.get("Signal") and not record.signal:
                record.signal = str(ctx.get("Signal") or "").strip() or None
            if ctx.get("Scanner_Score") is not None and record.scanner_score is None:
                record.scanner_score = _parse_float(ctx.get("Scanner_Score"))

            if record.unified_runtime_score is not None:
                record.rank_score = record.unified_runtime_score
            elif record.scanner_score is not None:
                record.rank_score = record.scanner_score

    def _load_candidates(self) -> dict[str, QueueCandidate]:
        merged: dict[str, QueueCandidate] = {}
        for artifact_name, priority, source_kind in TICKER_SOURCES:
            path = self.root / artifact_name
            rows = _read_csv_rows(path)
            status = self._register_source(artifact_name, path, len(rows))
            for row in rows:
                self._merge_row(
                    merged,
                    row,
                    artifact_name=artifact_name,
                    priority=priority,
                    source_kind=source_kind,
                    source_status=status,
                )
        return merged

    def _classify(
        self,
        record: QueueCandidate,
        watchlist: set[str],
        open_positions: set[str],
        *,
        exit_warning: bool = False,
    ) -> None:
        try:
            from markets.market_config import MARKETS
        except Exception:
            MARKETS = {}

        record.already_held = record.ticker in open_positions
        record.already_in_watchlist = record.ticker in watchlist
        record.market_open = _market_open_now(record.ticker, record.market_open)

        if record.source_status in {"STALE", "NO_DATA"}:
            record.classification = "STALE_SOURCE"
            record.reason = f"Primary source {record.source} status={record.source_status}"
            record.promotion_eligible = False
            return

        if record.already_held:
            record.classification = "ALREADY_HELD"
            record.reason = "Open position in portfolio.csv"
            record.promotion_eligible = False
            return

        if record.already_in_watchlist:
            record.classification = "ALREADY_IN_WATCHLIST"
            record.reason = "Already in watchlist.txt"
            record.promotion_eligible = False
            return

        if record.rank_score < MIN_MONITOR_RANK_SCORE:
            record.classification = "LOW_RANK"
            record.reason = f"rank_score {record.rank_score:.1f} < {MIN_MONITOR_RANK_SCORE}"
            record.promotion_eligible = False
            return

        if record.rank_score < MIN_RANK_SCORE:
            record.classification = "NEW_CANDIDATE"
            record.reason = (
                f"Tracked candidate rank={record.rank_score:.1f} below promotion threshold {MIN_RANK_SCORE}"
            )
            record.promotion_eligible = False
            return

        if record.market == "ASIA" and not MARKETS.get("ASIA", {}).get("enabled", False):
            record.classification = "MONITOR_ONLY"
            record.reason = "ASIA market disabled in market_config.py"
            record.promotion_eligible = False
            return

        if exit_warning and record.rank_score < MIN_RANK_SCORE + 15:
            record.classification = "MONITOR_ONLY"
            record.reason = f"Exit warning with moderate rank ({record.rank_score:.1f})"
            record.promotion_eligible = False
            return

        if not record.market_open:
            record.classification = "MARKET_CLOSED"
            record.reason = f"{record.market} market session closed"
            record.promotion_eligible = False
            return

        record.classification = "PROMOTION_ELIGIBLE"
        record.reason = (
            f"New candidate rank={record.rank_score:.1f}, {record.market} open, source={record.source}"
        )
        record.promotion_eligible = True

    def _resolve_recommended_action(
        self,
        promotion_eligible: list[QueueCandidate],
        market_closed: list[QueueCandidate],
        stale_count: int,
        sources_ok: bool,
    ) -> str:
        if stale_count > 0 or not sources_ok:
            return "REFRESH_SCANNER"
        if promotion_eligible:
            return "PROMOTE_MAX_10"
        if market_closed:
            return "WAIT_FOR_MARKET_OPEN"
        return "NO_ACTION"

    def build(self) -> dict[str, Any]:
        watchlist = _read_watchlist(self.root / WATCHLIST_FILE)
        watchlist_set = set(watchlist)
        open_positions = _read_open_positions(self.root / PORTFOLIO_FILE)
        advisory = _load_json(self.root / ADVISORY_FILE) or {}
        market_statuses = _market_statuses()

        merged = self._load_candidates()

        unified_by_ticker, unified_summary, unified_payload = self._load_unified_runtime()
        self._apply_runtime_bonuses(merged, unified_by_ticker)
        learning_global = unified_payload.get("learning_global") or {}

        exit_warnings: dict[str, bool] = {}
        ranking_path = self.root / "global_opportunity_ranking.csv"
        for row in _read_csv_rows(ranking_path):
            ticker = str(row.get("Ticker") or "").strip().upper()
            if ticker:
                exit_warnings[ticker] = _parse_bool(row.get("Exit_Warning"))

        for record in merged.values():
            self._classify(
                record,
                watchlist_set,
                open_positions,
                exit_warning=exit_warnings.get(record.ticker, False),
            )

        ranked = sorted(merged.values(), key=lambda r: (-r.rank_score, r.ticker))
        for index, record in enumerate(ranked, start=1):
            record.priority = index

        promotion_eligible = [r for r in ranked if r.classification == "PROMOTION_ELIGIBLE"]
        monitor_pool = [
            r
            for r in ranked
            if r.classification
            in {"PROMOTION_ELIGIBLE", "MARKET_CLOSED", "MONITOR_ONLY", "NEW_CANDIDATE"}
            and r.rank_score >= MIN_MONITOR_RANK_SCORE
        ]
        excluded = [
            r
            for r in ranked
            if r.classification in {"STALE_SOURCE", "LOW_RANK", "ALREADY_HELD", "ALREADY_IN_WATCHLIST"}
        ]

        top_10_promotion = promotion_eligible[:MAX_PROMOTION_ELIGIBLE]
        top_25_monitor = monitor_pool[:MAX_MONITOR]

        stale_count = sum(1 for r in ranked if r.classification == "STALE_SOURCE")
        sources_ok = any(
            self.sources_meta.get(name, {}).get("status") == "OK"
            for name, _, _ in TICKER_SOURCES
            if self.sources_meta.get(name, {}).get("present")
        )
        ranking_ok = self.sources_meta.get("global_opportunity_ranking.csv", {}).get("status") == "OK"
        global_data_sufficient = sources_ok and (
            ranking_ok or self.sources_meta.get("global_candidates.csv", {}).get("status") == "OK"
        )

        recommended_action = self._resolve_recommended_action(
            promotion_eligible,
            [r for r in ranked if r.classification == "MARKET_CLOSED"],
            stale_count,
            global_data_sufficient,
        )

        counts = {name: 0 for name in CLASSIFICATIONS}
        for record in ranked:
            counts[record.classification] = counts.get(record.classification, 0) + 1

        return {
            "schema": "tae.candidate_queue.v1",
            "mode": "CONTROLLED_INTEGRATION",
            "live_trading_impact": "NONE",
            "generated_at": _utc_now_iso(),
            "safety_mode": SAFETY_BANNER,
            "summary": {
                "total_candidates": len(ranked),
                "promotion_eligible_count": len(promotion_eligible),
                "already_held_count": counts.get("ALREADY_HELD", 0),
                "already_in_watchlist_count": counts.get("ALREADY_IN_WATCHLIST", 0),
                "market_closed_count": counts.get("MARKET_CLOSED", 0),
                "low_rank_count": counts.get("LOW_RANK", 0),
                "stale_source_count": counts.get("STALE_SOURCE", 0),
                "monitor_only_count": counts.get("MONITOR_ONLY", 0),
                "new_candidate_count": counts.get("NEW_CANDIDATE", 0),
                "current_watchlist_count": len(watchlist),
                "current_open_positions": len(open_positions),
                "global_data_sufficient": global_data_sufficient,
                "recommended_action": recommended_action,
                "unified_runtime_ssot": True,
                "ssot_record_count": unified_summary.get("record_count"),
                "learning_health_score": learning_global.get("Learning_Health_Score"),
                "unified_runtime_avg": (unified_summary.get("unified_runtime_score_summary") or {}).get(
                    "avg"
                ),
                "unified_runtime_confidence_avg": (
                    unified_summary.get("confidence_summary") or {}
                ).get("avg"),
            },
            "classification_counts": counts,
            "sources": self.sources_meta,
            "market_statuses": market_statuses,
            "advisory_snapshot": {
                "action": advisory.get("action")
                or (advisory.get("advisory") or {}).get("action"),
                "block_new_buy": advisory.get("block_new_buy"),
                "generated_at": advisory.get("generated_at"),
                "runtime_market_statuses": (advisory.get("runtime_snapshot") or {}).get(
                    "market_statuses"
                ),
            },
            "current_watchlist": watchlist,
            "current_open_positions": sorted(open_positions),
            "promotion_queue": {
                "top_10_promotion_eligible": [r.to_dict() for r in top_10_promotion],
                "top_25_monitor": [r.to_dict() for r in top_25_monitor],
                "excluded_with_reasons": [r.to_dict() for r in excluded],
                "recommended_action": recommended_action,
            },
            "candidates": [r.to_dict() for r in ranked],
        }


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    pq = report.get("promotion_queue") or {}
    lines = [
        "# TAE Global Candidate Queue",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']}",
        f"**Safety:** {report['safety_mode']}",
        "",
        "## Summary",
        "",
        f"- Total candidates processed: **{summary['total_candidates']}**",
        f"- Promotion eligible: **{summary['promotion_eligible_count']}**",
        f"- Already held: **{summary['already_held_count']}**",
        f"- Already in watchlist: **{summary['already_in_watchlist_count']}**",
        f"- Market closed: **{summary['market_closed_count']}**",
        f"- Recommended action: **{summary['recommended_action']}**",
        "",
        "## Promotion Queue",
        "",
        f"**Action:** {pq.get('recommended_action')}",
        "",
        "### Top 10 promotion eligible",
        "",
    ]
    top10 = pq.get("top_10_promotion_eligible") or []
    if top10:
        for item in top10:
            lines.append(
                f"- **{item['ticker']}** ({item['market']}) rank={item['rank_score']} "
                f"source=`{item['source']}` open={item['market_open']}"
            )
    else:
        lines.append("- *(none)*")

    lines.extend(["", "### Top 25 monitor", ""])
    for item in (pq.get("top_25_monitor") or [])[:10]:
        lines.append(
            f"- {item['ticker']} ({item['market']}) [{item['classification']}] "
            f"rank={item['rank_score']}"
        )
    if len(pq.get("top_25_monitor") or []) > 10:
        lines.append(f"- … and {len(pq['top_25_monitor']) - 10} more")

    lines.extend(["", "## Sources", ""])
    for name, meta in sorted((report.get("sources") or {}).items()):
        lines.append(
            f"- `{name}`: present={meta.get('present')} status={meta.get('status')} "
            f"rows={meta.get('row_count')} age_h={meta.get('age_hours')}"
        )

    lines.extend(
        [
            "",
            "## Governance",
            "",
            "- Feeds `tae_watchlist_proposal.py` when queue JSON present",
            "- Does **NOT** write `watchlist.txt`",
            "- Does **NOT** call `buy_position()` or modify BUY/SELL logic",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_csv(report: dict[str, Any], path: Path) -> None:
    fields = [
        "priority",
        "ticker",
        "market",
        "rank_score",
        "source",
        "scanner_score",
        "global_rank_score",
        "signal",
        "price",
        "already_held",
        "already_in_watchlist",
        "market_open",
        "promotion_eligible",
        "classification",
        "reason",
        "source_status",
        "sources_all",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for item in report.get("candidates") or []:
            row = dict(item)
            row["sources_all"] = "|".join(row.get("sources_all") or [])
            writer.writerow(row)


def main() -> int:
    root = Path(".")
    builder = CandidateQueueBuilder(root)
    report = builder.build()

    json_path = root / OUTPUT_JSON
    md_path = root / OUTPUT_MD
    csv_path = root / OUTPUT_CSV

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    _write_csv(report, csv_path)

    summary = report["summary"]
    pq = report["promotion_queue"]
    print("===== TAE GLOBAL CANDIDATE QUEUE =====")
    print(f"Safety: {SAFETY_BANNER}")
    print(f"Total candidates processed: {summary['total_candidates']}")
    print(f"Promotion eligible: {summary['promotion_eligible_count']}")
    print(f"Already held: {summary['already_held_count']}")
    print(f"Already in watchlist: {summary['already_in_watchlist_count']}")
    print(f"Market closed: {summary['market_closed_count']}")
    print(f"Recommended action: {summary['recommended_action']}")
    print("Top 10 promotion eligible:")
    for item in pq.get("top_10_promotion_eligible") or []:
        print(
            f"  - {item['ticker']} ({item['market']}) rank={item['rank_score']} "
            f"source={item['source']}"
        )
    if not pq.get("top_10_promotion_eligible"):
        print("  - (none)")
    print(f"Output: {json_path}, {md_path}, {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
