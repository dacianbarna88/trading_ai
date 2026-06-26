"""
Candidate Strategy Registry — Phase VIII B1

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Registers strategy candidates from Evidence Engine and Simulation Lab,
with FIFO-attributed metrics from portfolio.csv.
"""

from __future__ import annotations

import csv
import json
import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from research_core.strategy_evolution.candidate_report import (
    CandidateMetrics,
    CandidateRegistryReport,
    CandidateStatus,
    PromotionReadiness,
    RegistryVerdict,
    StrategyCandidate,
)

logger = logging.getLogger(__name__)

PORTFOLIO_PATH = Path("portfolio.csv")
EVIDENCE_REPORT_PATH = Path("tae_evidence_engine_report.json")
SIMULATION_LAB_PATH = Path("tae_continuous_strategy_simulation_lab.json")
INDEPENDENT_JSON = Path("tae_independent_double_entry_verification.json")
MIN_SHARES = 1e-9
PROMOTION_MIN_TRADES = 20


@dataclass
class _BuyLot:
    buy_id: int
    ticker: str
    buy_dt: datetime
    price: float
    shares: float
    score: float
    reason: str
    remaining: float
    realized_pnl: float = 0.0


@dataclass
class _BuyRecord:
    buy_id: int
    ticker: str
    score: float
    reason: str
    closed: bool
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float


@dataclass
class _CandidateDef:
    candidate_id: str
    title: str
    rule: str
    status: CandidateStatus
    source_evidence_id: str | None
    simulation_lab_strategy_id: str | None
    include: Callable[[_BuyRecord], bool]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_dt(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _has_closed_freeze(reason: str) -> bool:
    return "CLOSED_FREEZE" in (reason or "").upper()


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None
    return payload if isinstance(payload, dict) else None


def _candidate_definitions() -> list[_CandidateDef]:
    return [
        _CandidateDef(
            candidate_id="LIVE_BASELINE",
            title="Live baseline (actual portfolio BUYs)",
            rule="all BUY rows",
            status=CandidateStatus.LIVE_BASELINE,
            source_evidence_id=None,
            simulation_lab_strategy_id="BASELINE_ACTUAL",
            include=lambda b: True,
        ),
        _CandidateDef(
            candidate_id="SCORE_90_PLUS_NO_CLOSED_FREEZE",
            title="Score >= 90 excluding CLOSED_FREEZE",
            rule="Score >= 90 and Reason does not contain CLOSED_FREEZE",
            status=CandidateStatus.PAPER_CANDIDATE,
            source_evidence_id="simulation_best_score_90_plus_no_closed_freeze",
            simulation_lab_strategy_id="SCORE_90_PLUS_NO_CLOSED_FREEZE",
            include=lambda b: b.score >= 90 and not _has_closed_freeze(b.reason),
        ),
        _CandidateDef(
            candidate_id="SCORE_100_CURRENT_ONLY",
            title="Score >= 100 current (no CLOSED_FREEZE)",
            rule="Score >= 100 and Reason does not contain CLOSED_FREEZE",
            status=CandidateStatus.PAPER_CANDIDATE,
            source_evidence_id="score_100_current_not_defective",
            simulation_lab_strategy_id="SCORE_100_CURRENT_ONLY",
            include=lambda b: b.score >= 100 and not _has_closed_freeze(b.reason),
        ),
    ]


class CandidateStrategyRegistry:
    def __init__(
        self,
        portfolio_csv: Path | str = PORTFOLIO_PATH,
        evidence_report_path: Path | str = EVIDENCE_REPORT_PATH,
        simulation_lab_path: Path | str = SIMULATION_LAB_PATH,
    ) -> None:
        self._portfolio_csv = Path(portfolio_csv)
        self._evidence_report_path = Path(evidence_report_path)
        self._simulation_lab_path = Path(simulation_lab_path)

    def build(self) -> CandidateRegistryReport:
        evidence = _load_json(self._evidence_report_path)
        simulation = _load_json(self._simulation_lab_path)
        evidence_by_id = self._evidence_index(evidence)

        rows = self._read_csv(self._portfolio_csv)
        marks = self._latest_marks(rows)
        buys = self._build_buys(rows, marks)

        baseline_def = _candidate_definitions()[0]
        baseline_included = [b for b in buys if baseline_def.include(b)]
        baseline_metrics = self._compute_metrics(
            baseline_included,
            baseline_total_pnl=0.0,
            baseline_expectancy=0.0,
            is_baseline=True,
        )

        candidates: list[StrategyCandidate] = []
        for defn in _candidate_definitions():
            included = [b for b in buys if defn.include(b)]
            is_baseline = defn.candidate_id == baseline_def.candidate_id
            metrics = self._compute_metrics(
                included,
                baseline_total_pnl=baseline_metrics.total_pnl,
                baseline_expectancy=baseline_metrics.expectancy,
                is_baseline=is_baseline,
            )
            readiness = self._promotion_readiness(metrics, baseline_metrics)
            evidence_item = (
                evidence_by_id.get(defn.source_evidence_id)
                if defn.source_evidence_id
                else None
            )
            candidates.append(
                StrategyCandidate(
                    candidate_id=defn.candidate_id,
                    title=defn.title,
                    rule=defn.rule,
                    status=defn.status,
                    source_evidence_id=defn.source_evidence_id,
                    source_evidence_title=(
                        str(evidence_item.get("title")) if evidence_item else None
                    ),
                    metrics=metrics,
                    promotion_readiness=readiness,
                    simulation_lab_strategy_id=defn.simulation_lab_strategy_id,
                )
            )

        return CandidateRegistryReport(
            verdict=RegistryVerdict.CANDIDATE_STRATEGY_REGISTRY_READY,
            candidates=candidates,
            baseline_candidate_id="LIVE_BASELINE",
            evidence_engine_verdict=str(evidence.get("verdict")) if evidence else None,
            simulation_lab_verdict=str(simulation.get("verdict")) if simulation else None,
            sources_loaded={
                self._portfolio_csv.name: self._portfolio_csv.is_file(),
                self._evidence_report_path.name: evidence is not None,
                self._simulation_lab_path.name: simulation is not None,
            },
        )

    def _evidence_index(self, evidence: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        if not evidence:
            return {}
        items = evidence.get("evidence_items", [])
        if not isinstance(items, list):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for item in items:
            if isinstance(item, dict) and item.get("evidence_id"):
                out[str(item["evidence_id"])] = item
        return out

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        if not path.is_file():
            return []
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            return list(csv.DictReader(handle))

    def _latest_marks(self, rows: list[dict[str, str]]) -> dict[str, float]:
        marks: dict[str, float] = {}
        for row in rows:
            ticker = row.get("Ticker", "").strip()
            cp = _safe_float(row.get("Current_Price"))
            if ticker and cp > 0:
                marks[ticker] = cp
        independent = _load_json(INDEPENDENT_JSON)
        if independent:
            for pos in independent.get("open_positions", []):
                if isinstance(pos, dict):
                    ticker = str(pos.get("ticker", "")).strip()
                    price = _safe_float(pos.get("market_price"))
                    if ticker and price > 0:
                        marks[ticker] = price
        return marks

    def _build_buys(
        self,
        rows: list[dict[str, str]],
        marks: dict[str, float],
    ) -> list[_BuyRecord]:
        parsed: list[tuple[datetime, dict[str, str]]] = []
        for row in rows:
            dt = _parse_dt(row.get("Date", ""))
            if dt is not None:
                parsed.append((dt, row))
        parsed.sort(key=lambda x: x[0])

        fifo: dict[str, list[_BuyLot]] = defaultdict(list)
        lots_by_id: dict[int, _BuyLot] = {}
        buy_id = 0

        for dt, row in parsed:
            action = row.get("Action", "").upper()
            ticker = row.get("Ticker", "").strip()
            if not ticker or ticker == "CASH":
                continue
            price = _safe_float(row.get("Price"))
            shares = _safe_float(row.get("Shares"))

            if action == "BUY":
                buy_id += 1
                lot = _BuyLot(
                    buy_id=buy_id,
                    ticker=ticker,
                    buy_dt=dt,
                    price=price,
                    shares=shares,
                    score=_safe_float(row.get("Score")),
                    reason=row.get("Reason", "") or "",
                    remaining=shares,
                )
                fifo[ticker].append(lot)
                lots_by_id[buy_id] = lot
            elif action == "SELL":
                remaining = shares
                while remaining > MIN_SHARES and fifo[ticker]:
                    lot = fifo[ticker][0]
                    take = min(remaining, lot.remaining)
                    lot.realized_pnl += (price - lot.price) * take
                    lot.remaining -= take
                    remaining -= take
                    if lot.remaining <= MIN_SHARES:
                        fifo[ticker].pop(0)

        records: list[_BuyRecord] = []
        for lot in sorted(lots_by_id.values(), key=lambda x: (x.buy_dt, x.buy_id)):
            mark = marks.get(lot.ticker, lot.price)
            unrealized = (
                (mark - lot.price) * lot.remaining if lot.remaining > MIN_SHARES else 0.0
            )
            realized = round(lot.realized_pnl, 2)
            unrealized = round(unrealized, 2)
            closed = lot.remaining <= MIN_SHARES
            records.append(
                _BuyRecord(
                    buy_id=lot.buy_id,
                    ticker=lot.ticker,
                    score=lot.score,
                    reason=lot.reason,
                    closed=closed,
                    realized_pnl=realized,
                    unrealized_pnl=unrealized,
                    total_pnl=round(realized + unrealized, 2),
                )
            )
        return records

    def _compute_metrics(
        self,
        included: list[_BuyRecord],
        baseline_total_pnl: float,
        baseline_expectancy: float,
        is_baseline: bool = False,
    ) -> CandidateMetrics:
        pnls = [b.total_pnl for b in included]
        closed = [b for b in included if b.closed]
        open_trades = [b for b in included if not b.closed]
        winners = [b for b in closed if b.realized_pnl > 0.01]
        losers = [b for b in closed if b.realized_pnl < -0.01]

        gross_profit = sum(b.realized_pnl for b in winners)
        gross_loss = abs(sum(b.realized_pnl for b in losers))
        win_rate = (len(winners) / len(closed) * 100.0) if closed else 0.0
        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else (999.0 if gross_profit > 0 else 0.0)
        )
        expectancy = (
            sum(b.realized_pnl for b in closed) / len(closed) if closed else 0.0
        )
        total_pnl = sum(pnls) if pnls else 0.0
        delta_pnl = 0.0 if is_baseline else round(total_pnl - baseline_total_pnl, 2)
        delta_exp = 0.0 if is_baseline else round(expectancy - baseline_expectancy, 2)

        return CandidateMetrics(
            trades=len(included),
            closed_trades=len(closed),
            open_trades=len(open_trades),
            total_pnl=round(total_pnl, 2),
            avg_pnl=round(statistics.mean(pnls), 2) if pnls else 0.0,
            median_pnl=round(statistics.median(pnls), 2) if pnls else 0.0,
            win_rate=round(win_rate, 2),
            gross_profit=round(gross_profit, 2),
            gross_loss=round(gross_loss, 2),
            profit_factor=round(profit_factor, 4),
            expectancy=round(expectancy, 2),
            delta_vs_baseline_total_pnl=delta_pnl,
            delta_vs_baseline_expectancy=delta_exp,
        )

    def _promotion_readiness(
        self,
        metrics: CandidateMetrics,
        baseline: CandidateMetrics,
    ) -> PromotionReadiness:
        if metrics.trades >= PROMOTION_MIN_TRADES:
            if (
                metrics.profit_factor > baseline.profit_factor
                and metrics.expectancy > baseline.expectancy
                and metrics.total_pnl > baseline.total_pnl
            ):
                return PromotionReadiness.PROMOTION_REVIEW_ELIGIBLE
            return PromotionReadiness.NOT_READY
        if metrics.trades >= 1:
            return PromotionReadiness.PAPER_TRACKING
        return PromotionReadiness.NOT_READY
