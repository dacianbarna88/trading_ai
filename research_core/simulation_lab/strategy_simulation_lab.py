"""
Continuous Strategy Simulation Lab — Phase VII / IX.2C feeder

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Compares baseline portfolio BUY behavior against alternative entry filters.
Feeds candidate_registry — official conclusions via Strategy Evolution Daily Runner.
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
from typing import Callable

from research_core.simulation_lab.simulation_lab_report import (
    SimulationLabReport,
    SimulationLabVerdict,
    StrategyMetrics,
    StrategyRanking,
)
from research_core.strategy_evolution.pipeline_integration import (
    CANONICAL_PIPELINE_MODULE,
    pipeline_reference,
)

logger = logging.getLogger(__name__)

PIPELINE_ROLE = "FEEDER_READER"

PORTFOLIO_PATH = Path("portfolio.csv")
INDEPENDENT_JSON = Path("tae_independent_double_entry_verification.json")
MIN_SHARES = 1e-9


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
class SimulatedBuy:
    buy_id: int
    ticker: str
    score: float
    reason: str
    closed: bool
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float


@dataclass
class _StrategyDef:
    strategy_id: str
    label: str
    description: str
    include: Callable[[SimulatedBuy], bool]


def _safe_float(value, default: float = 0.0) -> float:
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


def _strategy_definitions() -> list[_StrategyDef]:
    return [
        _StrategyDef(
            strategy_id="BASELINE_ACTUAL",
            label="Baseline actual",
            description="All BUY rows as recorded in portfolio.csv",
            include=lambda b: True,
        ),
        _StrategyDef(
            strategy_id="EXCLUDE_LEGACY_CLOSED_FREEZE",
            label="Exclude CLOSED_FREEZE",
            description="Exclude BUY rows whose Reason contains CLOSED_FREEZE",
            include=lambda b: not _has_closed_freeze(b.reason),
        ),
        _StrategyDef(
            strategy_id="SCORE_90_TO_99_ONLY",
            label="Score 90–99 only",
            description="Include BUY rows with Score between 90 and 99 inclusive",
            include=lambda b: 90 <= b.score < 100,
        ),
        _StrategyDef(
            strategy_id="SCORE_100_CURRENT_ONLY",
            label="Score 100+ current",
            description="Score >= 100 excluding CLOSED_FREEZE reasons",
            include=lambda b: b.score >= 100 and not _has_closed_freeze(b.reason),
        ),
        _StrategyDef(
            strategy_id="SCORE_90_PLUS_NO_CLOSED_FREEZE",
            label="Score 90+ no freeze",
            description="Score >= 90 excluding CLOSED_FREEZE reasons",
            include=lambda b: b.score >= 90 and not _has_closed_freeze(b.reason),
        ),
    ]


class StrategySimulationLab:
    def __init__(self, portfolio_csv: Path | str = PORTFOLIO_PATH) -> None:
        self._portfolio_csv = Path(portfolio_csv)

    def run(self) -> SimulationLabReport:
        rows = self._read_csv(self._portfolio_csv)
        marks = self._latest_marks(rows)
        buys = self._build_buys(rows, marks)
        strategies = [self._metrics(defn, buys) for defn in _strategy_definitions()]

        best_pnl = max(strategies, key=lambda s: s.total_pnl)
        best_pf = max(strategies, key=lambda s: s.profit_factor)

        rankings: list[StrategyRanking] = []
        for metric_name, key_fn in (
            ("total_pnl", lambda s: s.total_pnl),
            ("profit_factor", lambda s: s.profit_factor),
            ("win_rate", lambda s: s.win_rate),
            ("expectancy", lambda s: s.expectancy),
        ):
            ordered = sorted(strategies, key=key_fn, reverse=True)
            for rank, strategy in enumerate(ordered, start=1):
                rankings.append(
                    StrategyRanking(
                        rank=rank,
                        strategy_id=strategy.strategy_id,
                        metric=metric_name,
                        metric_value=key_fn(strategy),
                    )
                )

        baseline = next(s for s in strategies if s.strategy_id == "BASELINE_ACTUAL")
        return SimulationLabReport(
            verdict=SimulationLabVerdict.CONTINUOUS_SIMULATION_LAB_READY,
            strategies=strategies,
            best_strategy_by_total_pnl=best_pnl.strategy_id,
            best_strategy_by_profit_factor=best_pf.strategy_id,
            strategy_rankings=rankings,
            baseline_total_pnl=baseline.total_pnl,
            buy_rows_total=len(buys),
            pipeline_reference={
                **pipeline_reference(),
                "pipeline_role": PIPELINE_ROLE,
                "feeds_module": "research_core/strategy_evolution/candidate_registry.py",
                "canonical_pipeline": CANONICAL_PIPELINE_MODULE,
            },
        )

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
        if INDEPENDENT_JSON.is_file():
            try:
                payload = json.loads(INDEPENDENT_JSON.read_text(encoding="utf-8"))
                for pos in payload.get("open_positions", []):
                    if isinstance(pos, dict):
                        ticker = str(pos.get("ticker", "")).strip()
                        price = _safe_float(pos.get("market_price"))
                        if ticker and price > 0:
                            marks[ticker] = price
            except (OSError, json.JSONDecodeError):
                pass
        return marks

    def _build_buys(
        self,
        rows: list[dict[str, str]],
        marks: dict[str, float],
    ) -> list[SimulatedBuy]:
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

        buys: list[SimulatedBuy] = []
        for lot in sorted(lots_by_id.values(), key=lambda x: (x.buy_dt, x.buy_id)):
            mark = marks.get(lot.ticker, lot.price)
            unrealized = (
                (mark - lot.price) * lot.remaining if lot.remaining > MIN_SHARES else 0.0
            )
            realized = round(lot.realized_pnl, 2)
            unrealized = round(unrealized, 2)
            buys.append(
                SimulatedBuy(
                    buy_id=lot.buy_id,
                    ticker=lot.ticker,
                    score=lot.score,
                    reason=lot.reason,
                    closed=lot.remaining <= MIN_SHARES,
                    realized_pnl=realized,
                    unrealized_pnl=unrealized,
                    total_pnl=round(realized + unrealized, 2),
                )
            )
        return buys

    def _metrics(self, defn: _StrategyDef, buys: list[SimulatedBuy]) -> StrategyMetrics:
        included = [b for b in buys if defn.include(b)]
        pnls = [b.total_pnl for b in included]
        closed = [b for b in included if b.closed]
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

        return StrategyMetrics(
            strategy_id=defn.strategy_id,
            label=defn.label,
            description=defn.description,
            trades=len(included),
            closed_trades=len(closed),
            total_pnl=round(sum(pnls), 2) if pnls else 0.0,
            avg_pnl=round(statistics.mean(pnls), 2) if pnls else 0.0,
            median_pnl=round(statistics.median(pnls), 2) if pnls else 0.0,
            win_rate=round(win_rate, 2),
            gross_profit=round(gross_profit, 2),
            gross_loss=round(gross_loss, 2),
            profit_factor=round(profit_factor, 4),
            expectancy=round(expectancy, 2),
        )
