"""
Score decomposition / Score 100+ anomaly analyzer — Phase VII Sprint A4

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Compares BUY cohorts Score 90–99 vs 100+ and inspects evidence dossiers when matchable.
"""

from __future__ import annotations

import csv
import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from research_core.score_decomposition.score_decomposition_report import (
    BuyTradeRecord,
    ComponentAverages,
    CohortMetrics,
    DOSSIER_COMPONENT_COLUMNS,
    GroupAggregate,
    PORTFOLIO_COMPONENT_COLUMNS,
    ScoreAnomalyVerdict,
    ScoreDecompositionReport,
    TraitSummary,
)

logger = logging.getLogger(__name__)

PORTFOLIO_PATH = Path("portfolio.csv")
DOSSIERS_PATH = Path("evidence_signal_dossiers.csv")
LIVE_SIGNALS_PATH = Path("live_signals.csv")
INDEPENDENT_JSON = Path("tae_independent_double_entry_verification.json")

MIN_SHARES = 1e-9
COHORT_90_99 = "90-99"
COHORT_100_PLUS = "100+"
ANOMALY_TOTAL_PNL_GAP = 75.0
MIN_COHORT_SIZE = 5
DOSSIER_MATCH_WINDOW_DAYS = 5
DOSSIER_MIN_MATCHES_FOR_COMPONENTS = 3


@dataclass
class _TrackedLot:
    buy_id: int
    ticker: str
    buy_dt: datetime
    buy_date: str
    price: float
    shares: float
    invested: float
    score: float
    signal: str
    reason: str
    region: str
    remaining: float
    realized_pnl: float = 0.0


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


def _parse_date_only(raw: str) -> datetime | None:
    dt = _parse_dt(raw)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0) if dt else None


def _region_for_ticker(ticker: str) -> str:
    upper = ticker.upper()
    if upper.endswith(".L"):
        return "UK"
    if any(upper.endswith(s) for s in (".DE", ".PA", ".AS", ".MI", ".SW", ".HE", ".ST")):
        return "Europe"
    return "US"


def _score_cohort(score: float) -> str | None:
    if 90 <= score < 100:
        return COHORT_90_99
    if score >= 100:
        return COHORT_100_PLUS
    return None


def _reason_trait(reason: str) -> str:
    ru = (reason or "").upper()
    if "CLOSED_FREEZE" in ru:
        return "CLOSED_FREEZE"
    if "DYNAMIC" in ru and "MARKET REGIME" in ru:
        return "DYNAMIC_MARKET_REGIME"
    if "AUTO STRONG BUY" in ru:
        return "AUTO_STRONG_BUY"
    return "OTHER"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


class ScoreDecompositionAnalyzer:
    def __init__(
        self,
        portfolio_csv: Path | str = PORTFOLIO_PATH,
        dossiers_csv: Path | str = DOSSIERS_PATH,
    ) -> None:
        self._portfolio_csv = Path(portfolio_csv)
        self._dossiers_csv = Path(dossiers_csv)

    def analyze(self) -> ScoreDecompositionReport:
        rows = _read_csv(self._portfolio_csv)
        marks = self._latest_marks(rows)
        portfolio_has_components = self._portfolio_has_score_components(rows)
        dossier_index = self._build_dossier_index()

        buys = self._build_cohort_buys(rows, marks, dossier_index)
        c90 = self._cohort_metrics(COHORT_90_99, [b for b in buys if b.cohort == COHORT_90_99])
        c100 = self._cohort_metrics(COHORT_100_PLUS, [b for b in buys if b.cohort == COHORT_100_PLUS])
        delta_total = c90.total_pnl - c100.total_pnl
        delta_median = c90.median_pnl - c100.median_pnl

        data_gaps: list[str] = []
        if not portfolio_has_components:
            data_gaps.append("DATA_GAP_SCORE_COMPONENTS_MISSING")

        matched = sum(1 for b in buys if b.dossier_matched)
        match_rate = (matched / len(buys) * 100.0) if buys else 0.0
        if matched < DOSSIER_MIN_MATCHES_FOR_COMPONENTS:
            data_gaps.append("DATA_GAP_DOSSIER_MATCH_INSUFFICIENT")

        groups = self._group_aggregates(buys)
        traits = self._score_100_loser_traits(buys)
        components = self._component_averages(buys, dossier_index)
        verdict = self._compute_verdict(
            c90,
            c100,
            delta_total,
            delta_median,
            matched,
            components,
            data_gaps,
        )

        return ScoreDecompositionReport(
            verdict=verdict,
            data_gaps=data_gaps,
            cohort_90_99=c90,
            cohort_100_plus=c100,
            cohort_delta_total_pnl=round(delta_total, 2),
            cohort_delta_median_pnl=round(delta_median, 2),
            dossier_match_count=matched,
            dossier_match_rate=round(match_rate, 2),
            group_aggregates=groups,
            score_100_loser_traits=traits,
            component_averages=components,
            buys=buys,
            live_signals_reference_rows=len(_read_csv(LIVE_SIGNALS_PATH)),
        )

    def _portfolio_has_score_components(self, rows: list[dict[str, str]]) -> bool:
        if not rows:
            return False
        headers = set(rows[0].keys())
        return any(col in headers for col in PORTFOLIO_COMPONENT_COLUMNS)

    def _latest_marks(self, rows: list[dict[str, str]]) -> dict[str, float]:
        marks: dict[str, float] = {}
        for row in rows:
            ticker = row.get("Ticker", "").strip()
            cp = _safe_float(row.get("Current_Price"))
            if ticker and cp > 0:
                marks[ticker] = cp
        if INDEPENDENT_JSON.is_file():
            try:
                import json

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

    def _build_dossier_index(self) -> dict[str, list[tuple[datetime, dict[str, str]]]]:
        index: dict[str, list[tuple[datetime, dict[str, str]]]] = defaultdict(list)
        for row in _read_csv(self._dossiers_csv):
            ticker = row.get("Ticker", "").strip()
            dt = _parse_date_only(row.get("Signal_Date", ""))
            if ticker and dt:
                index[ticker].append((dt, row))
        for ticker in index:
            index[ticker].sort(key=lambda x: x[0])
        return index

    def _match_dossier(
        self,
        ticker: str,
        buy_dt: datetime,
        index: dict[str, list[tuple[datetime, dict[str, str]]]],
    ) -> tuple[dict[str, str] | None, str]:
        candidates = index.get(ticker, [])
        if not candidates:
            return None, ""
        buy_day = buy_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        best: tuple[dict[str, str], datetime] | None = None
        best_delta = DOSSIER_MATCH_WINDOW_DAYS + 1
        for sig_dt, row in candidates:
            delta = abs((sig_dt - buy_day).days)
            if delta <= DOSSIER_MATCH_WINDOW_DAYS and delta < best_delta:
                best = (row, sig_dt)
                best_delta = delta
        if best is None:
            return None, ""
        return best[0], best[1].strftime("%Y-%m-%d")

    def _build_cohort_buys(
        self,
        rows: list[dict[str, str]],
        marks: dict[str, float],
        dossier_index: dict[str, list[tuple[datetime, dict[str, str]]]],
    ) -> list[BuyTradeRecord]:
        parsed: list[tuple[datetime, dict[str, str]]] = []
        for row in rows:
            dt = _parse_dt(row.get("Date", ""))
            if dt is not None:
                parsed.append((dt, row))
        parsed.sort(key=lambda x: x[0])

        fifo: dict[str, list[_TrackedLot]] = defaultdict(list)
        lots_by_id: dict[int, _TrackedLot] = {}
        buy_id = 0

        for dt, row in parsed:
            action = row.get("Action", "").upper()
            ticker = row.get("Ticker", "").strip()
            if not ticker or ticker == "CASH":
                continue
            price = _safe_float(row.get("Price"))
            shares = _safe_float(row.get("Shares"))
            score = _safe_float(row.get("Score"))
            cohort = _score_cohort(score)
            if action == "BUY" and cohort is None:
                continue

            if action == "BUY":
                buy_id += 1
                invested = _safe_float(row.get("Invested"))
                if invested <= 0:
                    invested = price * shares
                lot = _TrackedLot(
                    buy_id=buy_id,
                    ticker=ticker,
                    buy_dt=dt,
                    buy_date=row.get("Date", ""),
                    price=price,
                    shares=shares,
                    invested=invested,
                    score=score,
                    signal=row.get("Signal", "") or "",
                    reason=row.get("Reason", "") or "",
                    region=_region_for_ticker(ticker),
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

        records: list[BuyTradeRecord] = []
        for lot in sorted(lots_by_id.values(), key=lambda x: (x.buy_dt, x.buy_id)):
            mark = marks.get(lot.ticker, lot.price)
            unrealized = (
                (mark - lot.price) * lot.remaining if lot.remaining > MIN_SHARES else 0.0
            )
            dossier_row, dossier_date = self._match_dossier(
                lot.ticker, lot.buy_dt, dossier_index
            )
            records.append(
                BuyTradeRecord(
                    buy_id=lot.buy_id,
                    ticker=lot.ticker,
                    buy_date=lot.buy_date,
                    buy_price=lot.price,
                    shares=lot.shares,
                    invested=lot.invested,
                    score=lot.score,
                    cohort=_score_cohort(lot.score) or "",
                    signal=lot.signal,
                    reason=lot.reason,
                    region=lot.region,
                    closed=lot.remaining <= MIN_SHARES,
                    realized_pnl=round(lot.realized_pnl, 2),
                    unrealized_pnl=round(unrealized, 2),
                    total_pnl=round(lot.realized_pnl + unrealized, 2),
                    dossier_matched=dossier_row is not None,
                    dossier_signal_date=dossier_date,
                )
            )
        return records

    def _cohort_metrics(self, label: str, buys: list[BuyTradeRecord]) -> CohortMetrics:
        pnls = [b.total_pnl for b in buys]
        closed = [b for b in buys if b.closed]
        winners = [b for b in closed if b.realized_pnl > 0.01]
        losers = [b for b in closed if b.realized_pnl < -0.01]
        win_rate = (len(winners) / len(closed) * 100.0) if closed else 0.0
        avg = statistics.mean(pnls) if pnls else 0.0
        med = statistics.median(pnls) if pnls else 0.0
        return CohortMetrics(
            cohort=label,
            buy_count=len(buys),
            closed_count=len(closed),
            total_pnl=round(sum(pnls), 2),
            realized_pnl=round(sum(b.realized_pnl for b in buys), 2),
            unrealized_pnl=round(sum(b.unrealized_pnl for b in buys), 2),
            win_rate=round(win_rate, 2),
            average_pnl=round(avg, 2),
            median_pnl=round(med, 2),
            winner_count=len(winners),
            loser_count=len(losers),
        )

    def _group_aggregates(self, buys: list[BuyTradeRecord]) -> list[GroupAggregate]:
        out: list[GroupAggregate] = []
        for dimension, key_fn in (
            ("reason", lambda b: _reason_trait(b.reason)),
            ("ticker", lambda b: b.ticker),
            ("region", lambda b: b.region),
            ("signal", lambda b: b.signal or "UNKNOWN"),
        ):
            buckets: dict[tuple[str, str], list[BuyTradeRecord]] = defaultdict(list)
            for buy in buys:
                buckets[(buy.cohort, key_fn(buy))].append(buy)
            for (cohort, bucket), items in sorted(buckets.items()):
                total = sum(b.total_pnl for b in items)
                out.append(
                    GroupAggregate(
                        dimension=dimension,
                        bucket=bucket,
                        cohort=cohort,
                        buy_count=len(items),
                        total_pnl=round(total, 2),
                        average_pnl=round(total / len(items), 2) if items else 0.0,
                    )
                )
        return out

    def _score_100_loser_traits(self, buys: list[BuyTradeRecord]) -> list[TraitSummary]:
        losers = [
            b for b in buys if b.cohort == COHORT_100_PLUS and b.total_pnl < -0.01
        ]
        if not losers:
            return []

        trait_maps: dict[str, list[BuyTradeRecord]] = defaultdict(list)
        for buy in losers:
            trait_maps[f"reason:{_reason_trait(buy.reason)}"].append(buy)
            trait_maps[f"region:{buy.region}"].append(buy)
            trait_maps[f"ticker:{buy.ticker}"].append(buy)
            if "STOP LOSS" in buy.reason.upper() or any(
                b.realized_pnl < -50 for b in [buy]
            ):
                trait_maps["exit:stop_loss_or_deep_loss"].append(buy)

        summaries: list[TraitSummary] = []
        for trait, items in trait_maps.items():
            summaries.append(
                TraitSummary(
                    trait=trait,
                    count=len(items),
                    total_pnl=round(sum(b.total_pnl for b in items), 2),
                    examples=[f"{b.ticker}@{b.buy_date[:10]}" for b in items[:5]],
                )
            )
        summaries.sort(key=lambda t: (-t.count, t.total_pnl))
        return summaries[:10]

    def _component_averages(
        self,
        buys: list[BuyTradeRecord],
        dossier_index: dict[str, list[tuple[datetime, dict[str, str]]]],
    ) -> list[ComponentAverages]:
        matched_buys = [b for b in buys if b.dossier_matched]
        if len(matched_buys) < DOSSIER_MIN_MATCHES_FOR_COMPONENTS:
            return []

        out: list[ComponentAverages] = []
        for cohort in (COHORT_90_99, COHORT_100_PLUS):
            cohort_buys = [b for b in matched_buys if b.cohort == cohort]
            for subset, filt in (
                ("all", lambda b: True),
                ("losers", lambda b: b.total_pnl < -0.01),
                ("winners", lambda b: b.total_pnl > 0.01),
            ):
                subset_buys = [b for b in cohort_buys if filt(b)]
                if not subset_buys:
                    continue
                rows = []
                for buy in subset_buys:
                    row, _ = self._match_dossier(
                        buy.ticker,
                        _parse_dt(buy.buy_date) or datetime.min,
                        dossier_index,
                    )
                    if row:
                        rows.append(row)
                if not rows:
                    continue
                out.append(
                    ComponentAverages(
                        cohort=cohort,
                        subset=subset,
                        sample_count=len(rows),
                        momentum=self._avg_col(rows, "Momentum_Evidence_Score"),
                        trend=self._avg_col(rows, "Trend_Evidence_Score"),
                        volume=self._avg_col(rows, "Volume_Evidence_Score"),
                        risk=self._avg_col(rows, "Risk_Evidence_Score"),
                        conflict=self._avg_col(rows, "Conflict_Evidence_Score"),
                        overall=self._avg_col(rows, "Overall_Evidence_Score"),
                    )
                )
        return out

    def _avg_col(self, rows: list[dict[str, str]], col: str) -> float | None:
        vals = [_safe_float(r.get(col)) for r in rows if r.get(col) not in (None, "")]
        vals = [v for v in vals if v > 0 or col == "Conflict_Evidence_Score"]
        if not vals:
            return None
        return round(statistics.mean(vals), 2)

    def _compute_verdict(
        self,
        c90: CohortMetrics,
        c100: CohortMetrics,
        delta_total: float,
        delta_median: float,
        dossier_matches: int,
        components: list[ComponentAverages],
        data_gaps: list[str],
    ) -> ScoreAnomalyVerdict:
        if c100.buy_count < MIN_COHORT_SIZE or c90.buy_count < 3:
            return ScoreAnomalyVerdict.SCORE_100_NOT_STATISTICALLY_RELIABLE

        anomaly = (
            delta_total >= ANOMALY_TOTAL_PNL_GAP
            and c90.total_pnl > c100.total_pnl
        )

        if components and self._component_overweight_signal(components):
            return ScoreAnomalyVerdict.SCORE_COMPONENT_OVERWEIGHT_SUSPECTED

        if anomaly:
            return ScoreAnomalyVerdict.SCORE_100_ANOMALY_CONFIRMED

        if c100.buy_count < MIN_COHORT_SIZE or c90.buy_count < 3:
            return ScoreAnomalyVerdict.SCORE_100_NOT_STATISTICALLY_RELIABLE

        if (
            "DATA_GAP_SCORE_COMPONENTS_MISSING" in data_gaps
            and dossier_matches < DOSSIER_MIN_MATCHES_FOR_COMPONENTS
        ):
            return ScoreAnomalyVerdict.DATA_GAP_PREVENTS_ROOT_CAUSE

        return ScoreAnomalyVerdict.SCORE_100_NOT_STATISTICALLY_RELIABLE

    def _component_overweight_signal(self, components: list[ComponentAverages]) -> bool:
        losers = [
            c
            for c in components
            if c.cohort == COHORT_100_PLUS and c.subset == "losers" and c.sample_count >= 2
        ]
        winners = [
            c
            for c in components
            if c.cohort == COHORT_100_PLUS and c.subset == "winners" and c.sample_count >= 2
        ]
        if not losers or not winners:
            return False
        loser = losers[0]
        winner = winners[0]
        for attr in ("momentum", "conflict", "overall"):
            lv = getattr(loser, attr)
            wv = getattr(winner, attr)
            if lv is not None and wv is not None and lv - wv >= 8.0:
                return True
        return False
