#!/usr/bin/env python3
"""
TAE Global Intelligence Connector — Watchlist Proposal Adapter

PAPER_ONLY | ADVISORY_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE
Does NOT write watchlist.txt or modify live_bot.py.
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAFETY_BANNER = (
    "PAPER_ONLY | ADVISORY_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE | "
    "NO_WATCHLIST_WRITE"
)

DEFAULT_ROOT = Path(".")
WATCHLIST_FILE = "watchlist.txt"
PORTFOLIO_FILE = "portfolio.csv"
OUTPUT_JSON = "tae_watchlist_proposal.json"
OUTPUT_MD = "tae_watchlist_proposal.md"
OUTPUT_CSV = "tae_watchlist_proposal.csv"

CSV_STALE_MAX_AGE_HOURS = 168.0
JSON_STALE_MAX_AGE_HOURS = 72.0
MIN_RECOMMEND_RANK_SCORE = 40.0
MAX_RECOMMENDED_ADDITIONS = 10

TICKER_SOURCES: tuple[tuple[str, int, str], ...] = (
    ("global_opportunity_ranking.csv", 1, "global_ranking"),
    ("global_candidates.csv", 2, "global_candidates"),
    ("multi_market_candidates.csv", 3, "multi_market_scanner"),
    ("watchlist_candidates.csv", 4, "us_market_scanner"),
    ("watchlist_global.txt", 5, "watchlist_global"),
)

CONTEXT_SOURCES: tuple[tuple[str, str], ...] = (
    ("global_market_scanner.csv", "etf_regional_scanner"),
    ("regional_strength.csv", "regional_strength"),
    ("sector_rotation.csv", "sector_rotation"),
    ("tae_continuous_strategy_ranking.json", "strategy_ranking"),
    ("tae_candidate_strategy_registry.json", "strategy_registry"),
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


def _artifact_status(path: Path, *, json_artifact: bool = False) -> str:
    if not path.is_file():
        return "NO_DATA"
    age = _file_age_hours(path)
    if age is None:
        return "NO_DATA"
    limit = JSON_STALE_MAX_AGE_HOURS if json_artifact else CSV_STALE_MAX_AGE_HOURS
    return "STALE" if age > limit else "OK"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _json_generated_age_hours(payload: dict[str, Any] | None) -> float | None:
    if not payload:
        return None
    raw = payload.get("generated_at")
    if not raw:
        return _file_age_hours(Path(OUTPUT_JSON))
    text = str(raw).replace("Z", "+00:00")
    try:
        generated = datetime.fromisoformat(text)
    except ValueError:
        return None
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - generated).total_seconds() / 3600.0


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


def _read_ticker_list(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [
        line.strip().upper()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


@dataclass
class CandidateRecord:
    ticker: str
    market: str
    rank_score: float
    scanner_score: float | None = None
    global_rank_score: float | None = None
    signal: str | None = None
    price: float | None = None
    volume: float | None = None
    avg_volume_20: float | None = None
    exit_warning: bool = False
    market_open: bool | None = None
    primary_source: str = ""
    source_priority: int = 99
    sources_all: list[str] = field(default_factory=list)
    source_status: str = "NO_DATA"
    classification: str = "new_candidate"
    exclusion_reason: str | None = None
    monitor_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "market": self.market,
            "rank_score": round(self.rank_score, 4),
            "scanner_score": self.scanner_score,
            "global_rank_score": self.global_rank_score,
            "signal": self.signal,
            "price": self.price,
            "liquidity": {
                "volume": self.volume,
                "avg_volume_20": self.avg_volume_20,
            },
            "exit_warning": self.exit_warning,
            "market_open": self.market_open,
            "primary_source": self.primary_source,
            "source_priority": self.source_priority,
            "sources_all": list(self.sources_all),
            "source_status": self.source_status,
            "classification": self.classification,
            "exclusion_reason": self.exclusion_reason,
            "monitor_only": self.monitor_only,
        }


class WatchlistProposalBuilder:
    def __init__(self, root: Path | str = DEFAULT_ROOT) -> None:
        self.root = Path(root)
        self.sources_meta: dict[str, dict[str, Any]] = {}
        self.risk_notes: list[str] = []
        self.strategy_context: dict[str, Any] = {}

    def _register_source(
        self,
        name: str,
        path: Path,
        *,
        json_artifact: bool = False,
        row_count: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> str:
        status = _artifact_status(path, json_artifact=json_artifact)
        age_hours = _file_age_hours(path)
        if json_artifact and payload:
            gen_age = _json_generated_age_hours(payload)
            if gen_age is not None:
                age_hours = gen_age
                if gen_age > JSON_STALE_MAX_AGE_HOURS:
                    status = "STALE"
        meta = {
            "path": str(path),
            "present": path.is_file(),
            "status": status,
            "age_hours": round(age_hours, 2) if age_hours is not None else None,
            "row_count": row_count,
        }
        self.sources_meta[name] = meta
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
        merged: dict[str, CandidateRecord],
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

        if ticker not in merged or priority < merged[ticker].source_priority:
            record = merged.get(ticker) or CandidateRecord(
                ticker=ticker,
                market=market,
                rank_score=rank_score,
            )
            record.market = market
            record.rank_score = rank_score
            record.primary_source = artifact_name
            record.source_priority = priority
            record.source_status = source_status
            record.scanner_score = _parse_float(row.get("Score"))
            record.global_rank_score = _parse_float(row.get("Global_Rank_Score"))
            record.signal = str(row.get("Signal") or "").strip() or None
            record.price = _parse_float(row.get("Price"))
            record.volume = _parse_float(row.get("Volume"))
            record.avg_volume_20 = _parse_float(row.get("Avg_Volume_20"))
            record.exit_warning = _parse_bool(row.get("Exit_Warning"))
            if row.get("Market_Open") not in (None, ""):
                record.market_open = _parse_bool(row.get("Market_Open"))
            merged[ticker] = record
        else:
            record = merged[ticker]
            if record.scanner_score is None:
                record.scanner_score = _parse_float(row.get("Score"))
            if record.global_rank_score is None:
                record.global_rank_score = _parse_float(row.get("Global_Rank_Score"))

        if artifact_name not in merged[ticker].sources_all:
            merged[ticker].sources_all.append(artifact_name)

    def _load_ticker_sources(self) -> dict[str, CandidateRecord]:
        merged: dict[str, CandidateRecord] = {}

        for artifact_name, priority, source_kind in TICKER_SOURCES:
            path = self.root / artifact_name
            if artifact_name.endswith(".txt"):
                tickers = _read_ticker_list(path)
                status = self._register_source(artifact_name, path, row_count=len(tickers))
                for index, ticker in enumerate(tickers):
                    pseudo_row = {
                        "Ticker": ticker,
                        "Score": str(max(0, 100 - index)),
                    }
                    self._merge_row(
                        merged,
                        pseudo_row,
                        artifact_name=artifact_name,
                        priority=priority,
                        source_kind=source_kind,
                        source_status=status,
                    )
                continue

            rows = _read_csv_rows(path)
            status = self._register_source(artifact_name, path, row_count=len(rows))
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

    def _load_context_sources(self) -> None:
        for artifact_name, kind in CONTEXT_SOURCES:
            path = self.root / artifact_name
            if artifact_name.endswith(".json"):
                payload = _load_json(path)
                status = self._register_source(
                    artifact_name,
                    path,
                    json_artifact=True,
                    row_count=len(payload.get("rankings") or payload.get("candidates") or [])
                    if payload
                    else 0,
                    payload=payload,
                )
                if kind == "strategy_ranking" and payload:
                    top = (payload.get("rankings") or [])[:3]
                    self.strategy_context = {
                        "artifact": artifact_name,
                        "status": status,
                        "top_strategies": [
                            {
                                "candidate_id": item.get("candidate_id"),
                                "ranking_score": item.get("ranking_score"),
                                "decision": item.get("decision"),
                            }
                            for item in top
                            if isinstance(item, dict)
                        ],
                        "note": "Strategy-level ranking — not ticker selection.",
                    }
                elif kind == "strategy_registry" and payload:
                    self.strategy_context.setdefault("registry_verdict", payload.get("verdict"))
                continue

            rows = _read_csv_rows(path)
            status = self._register_source(artifact_name, path, row_count=len(rows))
            if kind == "regional_strength" and rows:
                parts = [
                    f"{row.get('Region')}={row.get('Regional_Strength')}"
                    for row in rows[:4]
                    if row.get("Region")
                ]
                if parts:
                    self.risk_notes.append(
                        f"Regional strength ({artifact_name}, {status}): {', '.join(parts)}"
                    )
            elif kind == "sector_rotation" and rows:
                leaders = sorted(
                    rows,
                    key=lambda r: _parse_float(r.get("Sector_Score")) or -999.0,
                    reverse=True,
                )[:3]
                leader_txt = ", ".join(
                    f"{r.get('Sector')}({r.get('Sector_Score')})" for r in leaders if r.get("Sector")
                )
                if leader_txt:
                    self.risk_notes.append(
                        f"Sector rotation leaders ({artifact_name}, {status}): {leader_txt}"
                    )
            elif kind == "etf_regional_scanner" and rows:
                leaders = sorted(
                    rows,
                    key=lambda r: _parse_float(r.get("Strategic_Score")) or -999.0,
                    reverse=True,
                )[:3]
                leader_txt = ", ".join(
                    f"{r.get('Market')}({r.get('Strategic_Score')})" for r in leaders if r.get("Market")
                )
                if leader_txt:
                    self.risk_notes.append(
                        f"ETF regional scanner leaders ({artifact_name}, {status}): {leader_txt}"
                    )

    def _classify_candidates(
        self,
        merged: dict[str, CandidateRecord],
        watchlist: set[str],
        open_positions: set[str],
    ) -> None:
        try:
            from markets.market_config import MARKETS
        except Exception:
            MARKETS = {}

        for record in merged.values():
            if record.ticker in watchlist:
                record.classification = "already_in_watchlist"
                record.exclusion_reason = "Already in watchlist.txt"
            elif record.ticker in open_positions:
                record.classification = "already_held"
                record.exclusion_reason = "Open position in portfolio.csv"
                record.monitor_only = True
            elif record.market == "ASIA" and not MARKETS.get("ASIA", {}).get("enabled", False):
                record.classification = "excluded"
                record.exclusion_reason = "ASIA market disabled in market_config.py"
            elif record.exit_warning and record.rank_score < MIN_RECOMMEND_RANK_SCORE:
                record.classification = "excluded"
                record.exclusion_reason = (
                    f"Exit warning with low rank score ({record.rank_score:.1f})"
                )
            elif record.source_status == "STALE":
                record.classification = "excluded"
                record.exclusion_reason = f"Primary source stale: {record.primary_source}"
            elif record.source_status == "NO_DATA":
                record.classification = "excluded"
                record.exclusion_reason = f"No data from primary source: {record.primary_source}"
            else:
                record.classification = "new_candidate"
                record.exclusion_reason = None

    def build(self) -> dict[str, Any]:
        watchlist = _read_watchlist(self.root / WATCHLIST_FILE)
        watchlist_set = set(watchlist)
        open_positions = _read_open_positions(self.root / PORTFOLIO_FILE)

        self._load_context_sources()
        merged = self._load_ticker_sources()
        self._classify_candidates(merged, watchlist_set, open_positions)

        ranked = sorted(merged.values(), key=lambda r: (-r.rank_score, r.ticker))
        by_market: dict[str, list[dict[str, Any]]] = {"US": [], "EU": [], "UK": [], "ASIA": []}
        for record in ranked:
            market = record.market if record.market in by_market else "US"
            by_market[market].append(record.to_dict())

        already_in_watchlist = [r.to_dict() for r in ranked if r.classification == "already_in_watchlist"]
        already_held = [r.to_dict() for r in ranked if r.classification == "already_held"]
        new_candidates = [r.to_dict() for r in ranked if r.classification == "new_candidate"]
        excluded = [r.to_dict() for r in ranked if r.classification == "excluded"]

        recommended = [
            r.to_dict()
            for r in ranked
            if r.classification == "new_candidate" and r.rank_score >= MIN_RECOMMEND_RANK_SCORE
        ][:MAX_RECOMMENDED_ADDITIONS]

        primary_sources_ok = any(
            self.sources_meta.get(name, {}).get("status") == "OK"
            for name, _, _ in TICKER_SOURCES
            if self.sources_meta.get(name, {}).get("present")
        )
        ranking_ok = self.sources_meta.get("global_opportunity_ranking.csv", {}).get("status") == "OK"
        global_data_sufficient = primary_sources_ok and (
            ranking_ok or self.sources_meta.get("global_candidates.csv", {}).get("status") == "OK"
        )

        sources_found = [name for name, meta in self.sources_meta.items() if meta.get("present")]
        sources_missing = [name for name, meta in self.sources_meta.items() if not meta.get("present")]

        stale_sources = [
            name for name, meta in self.sources_meta.items() if meta.get("status") == "STALE"
        ]
        if stale_sources:
            self.risk_notes.append(f"Stale source artifacts: {', '.join(sorted(stale_sources))}")
        if not global_data_sufficient:
            self.risk_notes.append(
                "Insufficient fresh global ranking/scanner data — proposals are advisory only."
            )
        if len(recommended) == 0 and len(new_candidates) > 0:
            self.risk_notes.append(
                "New candidates exist but none meet recommendation threshold or all were filtered."
            )
        if len(recommended) == 0 and len(new_candidates) == 0:
            self.risk_notes.append(
                "Watchlist already covers all ranked scanner candidates; no additions proposed."
            )

        self.risk_notes.append(
            "This proposal does NOT modify watchlist.txt — operator review required."
        )

        summary = {
            "current_watchlist_count": len(watchlist),
            "current_open_positions": len(open_positions),
            "candidate_count": len(ranked),
            "new_candidate_count": len(new_candidates),
            "recommended_additions_count": len(recommended),
            "sources_found": sources_found,
            "sources_missing": sources_missing,
            "global_data_sufficient": global_data_sufficient,
        }

        return {
            "schema": "tae.watchlist_proposal.v1",
            "mode": "PAPER_ONLY_ADVISORY",
            "live_trading_impact": "NONE",
            "generated_at": _utc_now_iso(),
            "safety_mode": SAFETY_BANNER,
            "summary": summary,
            "sources": self.sources_meta,
            "current_watchlist": watchlist,
            "current_open_positions": sorted(open_positions),
            "top_10": [r.to_dict() for r in ranked[:10]],
            "top_25": [r.to_dict() for r in ranked[:25]],
            "top_50": [r.to_dict() for r in ranked[:50]],
            "by_market": by_market,
            "already_in_watchlist": already_in_watchlist,
            "already_held": already_held,
            "new_candidates": new_candidates,
            "excluded_candidates": excluded,
            "recommended_additions_max_10": recommended,
            "risk_notes": self.risk_notes,
            "strategy_context": self.strategy_context,
        }


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# TAE Watchlist Proposal",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']}",
        f"**Safety:** {report['safety_mode']}",
        "",
        "## Summary",
        "",
        f"- Current watchlist count: **{summary['current_watchlist_count']}**",
        f"- Open positions: **{summary['current_open_positions']}**",
        f"- Candidates consumed: **{summary['candidate_count']}**",
        f"- New candidates: **{summary['new_candidate_count']}**",
        f"- Recommended additions (max 10): **{summary['recommended_additions_count']}**",
        f"- Global data sufficient: **{summary['global_data_sufficient']}**",
        "",
        "## Sources",
        "",
    ]
    for name, meta in sorted((report.get("sources") or {}).items()):
        lines.append(
            f"- `{name}`: present={meta.get('present')} status={meta.get('status')} "
            f"rows={meta.get('row_count')} age_h={meta.get('age_hours')}"
        )

    lines.extend(["", "## Recommended Additions (max 10)", ""])
    recs = report.get("recommended_additions_max_10") or []
    if recs:
        for item in recs:
            lines.append(
                f"- **{item['ticker']}** ({item['market']}) rank={item['rank_score']} "
                f"source=`{item['primary_source']}` signal={item.get('signal')}"
            )
    else:
        lines.append("- *(none)*")

    lines.extend(["", "## Top 10 (all sources)", ""])
    for item in report.get("top_10") or []:
        lines.append(
            f"- {item['ticker']} ({item['market']}) rank={item['rank_score']} "
            f"[{item['classification']}] source={item['primary_source']}"
        )

    lines.extend(["", "## Risk Notes", ""])
    for note in report.get("risk_notes") or []:
        lines.append(f"- {note}")

    lines.extend(["", "## Strategy Context (non-ticker)", ""])
    ctx = report.get("strategy_context") or {}
    if ctx:
        lines.append(f"- Registry verdict: {ctx.get('registry_verdict')}")
        for strat in ctx.get("top_strategies") or []:
            lines.append(
                f"- Strategy `{strat.get('candidate_id')}` score={strat.get('ranking_score')} "
                f"decision={strat.get('decision')}"
            )
    else:
        lines.append("- *(none)*")

    lines.extend(
        [
            "",
            "## Governance",
            "",
            "- Does **NOT** write `watchlist.txt`",
            "- Does **NOT** execute trades",
            "- Operator must manually review before any watchlist change",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_csv(report: dict[str, Any], path: Path) -> None:
    fields = [
        "ticker",
        "market",
        "rank_score",
        "scanner_score",
        "global_rank_score",
        "signal",
        "price",
        "volume",
        "avg_volume_20",
        "exit_warning",
        "market_open",
        "classification",
        "exclusion_reason",
        "primary_source",
        "source_status",
        "sources_all",
        "monitor_only",
    ]
    rows: list[dict[str, Any]] = []
    for bucket in (
        "top_50",
        "already_in_watchlist",
        "already_held",
        "new_candidates",
        "excluded_candidates",
    ):
        for item in report.get(bucket) or []:
            if any(existing["ticker"] == item["ticker"] for existing in rows):
                continue
            flat = dict(item)
            liquidity = flat.pop("liquidity", {}) or {}
            flat["volume"] = liquidity.get("volume")
            flat["avg_volume_20"] = liquidity.get("avg_volume_20")
            flat["sources_all"] = "|".join(flat.get("sources_all") or [])
            rows.append(flat)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(rows, key=lambda r: (-float(r.get("rank_score") or 0), r["ticker"])):
            writer.writerow(row)


def main() -> int:
    root = Path(".")
    builder = WatchlistProposalBuilder(root)
    report = builder.build()

    json_path = root / OUTPUT_JSON
    md_path = root / OUTPUT_MD
    csv_path = root / OUTPUT_CSV

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    _write_csv(report, csv_path)

    summary = report["summary"]
    print("===== TAE WATCHLIST PROPOSAL ADAPTER =====")
    print(f"Safety: {SAFETY_BANNER}")
    print(f"Watchlist count: {summary['current_watchlist_count']}")
    print(f"Open positions: {summary['current_open_positions']}")
    print(f"Candidates consumed: {summary['candidate_count']}")
    print(f"New candidates: {summary['new_candidate_count']}")
    print(f"Recommended additions: {summary['recommended_additions_count']}")
    print(f"Global data sufficient: {summary['global_data_sufficient']}")
    print(f"Sources found: {len(summary['sources_found'])} | missing: {len(summary['sources_missing'])}")
    if summary["sources_missing"]:
        print("  missing:", ", ".join(summary["sources_missing"]))
    print("Recommended:")
    for item in report.get("recommended_additions_max_10") or []:
        print(
            f"  - {item['ticker']} ({item['market']}) rank={item['rank_score']} "
            f"source={item['primary_source']}"
        )
    if not report.get("recommended_additions_max_10"):
        print("  - (none)")
    print(f"Output: {json_path}, {md_path}, {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
