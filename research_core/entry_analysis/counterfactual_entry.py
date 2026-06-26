"""
Counterfactual entry analyzer — Phase VII Sprint A3

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Simulates alternative entry filters and sizing rules on historical BUY rows.
"""

from __future__ import annotations

import csv
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from research_core.entry_analysis.entry_analysis_report import (
    BaselineMetrics,
    BucketPnL,
    EntryBuyRecord,
    EntryCounterfactualReport,
    EntryRecommendation,
    EntryVerdict,
    ExternalRefs,
    RecommendationRisk,
    SCORE_BUCKETS,
    ScenarioResult,
)

logger = logging.getLogger(__name__)

PORTFOLIO_PATH = Path("portfolio.csv")
LIVE_SIGNALS_PATH = Path("live_signals.csv")
ALERTS_LOG_PATH = Path("alerts_log.csv")
ATTRIBUTION_JSON = Path("tae_profit_attribution.json")
INDEPENDENT_JSON = Path("tae_independent_double_entry_verification.json")

MIN_SHARES = 1e-9
VERDICT_DELTA_THRESHOLD = 50.0
EUROPE_SUFFIXES = (".DE", ".PA", ".AS", ".MI", ".SW", ".BR", ".HE", ".ST")
UK_SUFFIX = ".L"

SIZE_BUCKETS = [
    ("micro", 0, 100),
    ("small", 100, 500),
    ("medium", 500, 2000),
    ("large", 2000, 5000),
    ("xlarge", 5000, 1e12),
]

FILTER_SCENARIO_IDS = frozenset({
    "skip_score_lt_80",
    "skip_score_lt_90",
    "skip_score_lt_100",
    "skip_not_strong_buy",
    "skip_stop_loss_exit",
})

SIZING_SCENARIO_IDS = frozenset({
    "half_size_score_lt_90",
    "double_size_score_gte_100",
    "proportional_score",
})


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
    had_stop_loss_exit: bool = False


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


def _region_for_ticker(ticker: str) -> str:
    upper = ticker.upper()
    if upper.endswith(UK_SUFFIX):
        return "UK"
    for suffix in EUROPE_SUFFIXES:
        if upper.endswith(suffix):
            return "Europe"
    return "US"


def _is_stop_loss(reason: str, signal: str) -> bool:
    text = f"{reason} {signal}".upper()
    return "STOP LOSS" in text or "STOP_LOSS" in text


def _score_bucket(score: float) -> str:
    for label, lo, hi in SCORE_BUCKETS:
        if lo <= score <= hi:
            return label
    return "0-39"


def _size_bucket(invested: float) -> str:
    for label, lo, hi in SIZE_BUCKETS:
        if lo <= invested < hi:
            return label
    return "xlarge"


def _reason_bucket(reason: str) -> str:
    ru = (reason or "").upper()
    if "AUTO STRONG BUY" in ru:
        return "AUTO_STRONG_BUY"
    if "CLOSED_FREEZE" in ru:
        return "CLOSED_FREEZE"
    if "REBALANCE" in ru or "REDUCE" in ru or "SIMULATION" in ru:
        return "SIMULATION"
    if "DEPOSIT" in ru:
        return "DEPOSIT"
    return "OTHER"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None
    return payload if isinstance(payload, dict) else None


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


ScenarioMultiplier = Callable[[EntryBuyRecord], float]


class CounterfactualEntryAnalyzer:
    def __init__(
        self,
        portfolio_csv: Path | str = PORTFOLIO_PATH,
    ) -> None:
        self._portfolio_csv = Path(portfolio_csv)

    def analyze(self) -> EntryCounterfactualReport:
        rows = _read_csv_rows(self._portfolio_csv)
        marks = self._latest_marks(rows)
        buys = self._build_buy_records(rows, marks)
        baseline = self._baseline_metrics(buys)

        scenarios = [
            self._run_scenario(
                buys,
                baseline,
                "skip_score_lt_80",
                "Skip Score < 80",
                lambda b: 0.0 if b.score < 80 else 1.0,
            ),
            self._run_scenario(
                buys,
                baseline,
                "skip_score_lt_90",
                "Skip Score < 90",
                lambda b: 0.0 if b.score < 90 else 1.0,
            ),
            self._run_scenario(
                buys,
                baseline,
                "skip_score_lt_100",
                "Skip Score < 100",
                lambda b: 0.0 if b.score < 100 else 1.0,
            ),
            self._run_scenario(
                buys,
                baseline,
                "skip_not_strong_buy",
                "Skip Signal != STRONG BUY",
                lambda b: 0.0 if b.signal.upper() != "STRONG BUY" else 1.0,
            ),
            self._run_scenario(
                buys,
                baseline,
                "skip_stop_loss_exit",
                "Skip BUY later STOP LOSS exit",
                lambda b: 0.0 if b.had_stop_loss_exit else 1.0,
            ),
            self._run_scenario(
                buys,
                baseline,
                "half_size_score_lt_90",
                "Half-size Score < 90",
                lambda b: 0.5 if b.score < 90 else 1.0,
            ),
            self._run_scenario(
                buys,
                baseline,
                "double_size_score_gte_100",
                "Double-size Score >= 100",
                lambda b: 2.0 if b.score >= 100 else 1.0,
            ),
            self._run_scenario(
                buys,
                baseline,
                "proportional_score",
                "Capital proportional to Score",
                lambda b: max(0.0, b.score / 100.0),
            ),
        ]

        best = max(scenarios, key=lambda s: s.hypothetical_total_pnl)
        worst = min(scenarios, key=lambda s: s.hypothetical_total_pnl)
        external = self._external_refs(baseline.total_pnl)
        verdict = self._compute_verdict(scenarios)
        recommendations = self._build_recommendations(verdict, scenarios, buys)

        return EntryCounterfactualReport(
            verdict=verdict,
            baseline=baseline,
            scenarios=scenarios,
            best_scenario_id=best.scenario_id,
            worst_scenario_id=worst.scenario_id,
            buys=buys,
            pnl_by_score_bucket=self._aggregate_buckets(buys, lambda b: _score_bucket(b.score)),
            pnl_by_signal=self._aggregate_buckets(buys, lambda b: b.signal or "UNKNOWN"),
            pnl_by_reason=self._aggregate_buckets(buys, lambda b: _reason_bucket(b.reason)),
            pnl_by_region=self._aggregate_buckets(buys, lambda b: b.region),
            pnl_by_size_bucket=self._aggregate_buckets(buys, lambda b: _size_bucket(b.invested)),
            recommendations=recommendations,
            external_refs=external,
        )

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
                if not isinstance(pos, dict):
                    continue
                ticker = str(pos.get("ticker", "")).strip()
                price = _safe_float(pos.get("market_price"))
                if ticker and price > 0:
                    marks[ticker] = price
        return marks

    def _build_buy_records(
        self,
        rows: list[dict[str, str]],
        marks: dict[str, float],
    ) -> list[EntryBuyRecord]:
        parsed: list[tuple[datetime, dict[str, str]]] = []
        for row in rows:
            dt = _parse_dt(row.get("Date", ""))
            if dt is None:
                continue
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
            signal = row.get("Signal", "") or ""
            reason = row.get("Reason", "") or ""
            invested = _safe_float(row.get("Invested"))
            if invested <= 0 and price > 0 and shares > 0:
                invested = price * shares

            if action == "BUY":
                buy_id += 1
                lot = _TrackedLot(
                    buy_id=buy_id,
                    ticker=ticker,
                    buy_dt=dt,
                    buy_date=row.get("Date", ""),
                    price=price,
                    shares=shares,
                    invested=invested,
                    score=score,
                    signal=signal,
                    reason=reason,
                    region=_region_for_ticker(ticker),
                    remaining=shares,
                )
                fifo[ticker].append(lot)
                lots_by_id[buy_id] = lot
            elif action == "SELL":
                remaining = shares
                stop = _is_stop_loss(reason, signal)
                while remaining > MIN_SHARES and fifo[ticker]:
                    lot = fifo[ticker][0]
                    take = min(remaining, lot.remaining)
                    lot.realized_pnl += (price - lot.price) * take
                    if stop:
                        lot.had_stop_loss_exit = True
                    lot.remaining -= take
                    remaining -= take
                    if lot.remaining <= MIN_SHARES:
                        fifo[ticker].pop(0)

        records: list[EntryBuyRecord] = []
        for lot in sorted(lots_by_id.values(), key=lambda x: (x.buy_dt, x.buy_id)):
            mark = marks.get(lot.ticker, lot.price)
            unrealized = (mark - lot.price) * lot.remaining if lot.remaining > MIN_SHARES else 0.0
            closed = lot.remaining <= MIN_SHARES
            total = lot.realized_pnl + unrealized
            records.append(
                EntryBuyRecord(
                    buy_id=lot.buy_id,
                    ticker=lot.ticker,
                    buy_date=lot.buy_date,
                    buy_price=lot.price,
                    shares=lot.shares,
                    invested=lot.invested,
                    score=lot.score,
                    signal=lot.signal,
                    reason=lot.reason,
                    region=lot.region,
                    closed=closed,
                    had_stop_loss_exit=lot.had_stop_loss_exit,
                    realized_pnl=round(lot.realized_pnl, 2),
                    unrealized_pnl=round(unrealized, 2),
                    total_pnl=round(total, 2),
                )
            )
        return records

    def _baseline_metrics(self, buys: list[EntryBuyRecord]) -> BaselineMetrics:
        realized = sum(b.realized_pnl for b in buys)
        open_pnl = sum(b.unrealized_pnl for b in buys)
        total = realized + open_pnl
        closed = [b for b in buys if b.closed]
        wins = [b for b in closed if b.realized_pnl > 0.01]
        losses = [b for b in closed if b.realized_pnl < -0.01]
        gross_profit = sum(b.realized_pnl for b in wins)
        gross_loss = abs(sum(b.realized_pnl for b in losses))
        win_rate = (len(wins) / len(closed) * 100.0) if closed else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (
            gross_profit if gross_profit > 0 else 0.0
        )
        expectancy = (sum(b.realized_pnl for b in closed) / len(closed)) if closed else 0.0
        open_count = sum(1 for b in buys if not b.closed)

        return BaselineMetrics(
            realized_pnl=round(realized, 2),
            open_pnl=round(open_pnl, 2),
            total_pnl=round(total, 2),
            win_rate=round(win_rate, 2),
            profit_factor=round(profit_factor, 4),
            expectancy=round(expectancy, 2),
            buy_count=len(buys),
            closed_buy_count=len(closed),
            open_buy_count=open_count,
        )

    def _run_scenario(
        self,
        buys: list[EntryBuyRecord],
        baseline: BaselineMetrics,
        scenario_id: str,
        label: str,
        multiplier_fn: ScenarioMultiplier,
    ) -> ScenarioResult:
        hyp_realized = 0.0
        hyp_open = 0.0
        skipped = 0
        capital_avoided = 0.0
        winners_lost = 0.0
        losers_avoided = 0.0

        for buy in buys:
            mult = multiplier_fn(buy)
            if mult <= MIN_SHARES:
                skipped += 1
                capital_avoided += buy.invested
                if buy.total_pnl > 0.01:
                    winners_lost += buy.total_pnl
                elif buy.total_pnl < -0.01:
                    losers_avoided += abs(buy.total_pnl)
                continue
            hyp_realized += buy.realized_pnl * mult
            hyp_open += buy.unrealized_pnl * mult

        hyp_total = hyp_realized + hyp_open
        return ScenarioResult(
            scenario_id=scenario_id,
            label=label,
            hypothetical_realized_pnl=round(hyp_realized, 2),
            hypothetical_open_pnl=round(hyp_open, 2),
            hypothetical_total_pnl=round(hyp_total, 2),
            delta_vs_baseline=round(hyp_total - baseline.total_pnl, 2),
            trades_skipped=skipped,
            capital_avoided=round(capital_avoided, 2),
            winners_lost=round(winners_lost, 2),
            losers_avoided=round(losers_avoided, 2),
        )

    def _aggregate_buckets(
        self,
        buys: list[EntryBuyRecord],
        key_fn: Callable[[EntryBuyRecord], str],
    ) -> list[BucketPnL]:
        buckets: dict[str, list[EntryBuyRecord]] = defaultdict(list)
        for buy in buys:
            buckets[key_fn(buy)].append(buy)
        out: list[BucketPnL] = []
        for bucket in sorted(buckets.keys()):
            items = buckets[bucket]
            out.append(
                BucketPnL(
                    bucket=bucket,
                    realized_pnl=round(sum(b.realized_pnl for b in items), 2),
                    unrealized_pnl=round(sum(b.unrealized_pnl for b in items), 2),
                    total_pnl=round(sum(b.total_pnl for b in items), 2),
                    buy_count=len(items),
                )
            )
        return out

    def _external_refs(self, baseline_total: float) -> ExternalRefs:
        attr = _load_json(ATTRIBUTION_JSON)
        indep = _load_json(INDEPENDENT_JSON)
        attr_total = None
        indep_total = None
        if attr and isinstance(attr.get("core"), dict):
            attr_total = _safe_float(attr["core"].get("total_pnl"))
        if indep:
            indep_total = _safe_float(indep.get("independent_total_pnl"))
        delta = round(baseline_total - attr_total, 2) if attr_total is not None else None
        return ExternalRefs(
            profit_attribution_total_pnl=attr_total,
            independent_verification_total_pnl=indep_total,
            baseline_delta_vs_attribution=delta,
            live_signals_rows=len(_read_csv_rows(LIVE_SIGNALS_PATH)),
            alerts_log_rows=len(_read_csv_rows(ALERTS_LOG_PATH)),
        )

    def _compute_verdict(self, scenarios: list[ScenarioResult]) -> EntryVerdict:
        filter_deltas = [
            s.delta_vs_baseline for s in scenarios if s.scenario_id in FILTER_SCENARIO_IDS
        ]
        sizing_deltas = [
            s.delta_vs_baseline for s in scenarios if s.scenario_id in SIZING_SCENARIO_IDS
        ]
        all_deltas = [s.delta_vs_baseline for s in scenarios]

        best_filter = max(filter_deltas) if filter_deltas else 0.0
        best_sizing = max(sizing_deltas) if sizing_deltas else 0.0
        best_any = max(all_deltas) if all_deltas else 0.0
        worst_any = min(all_deltas) if all_deltas else 0.0

        if best_filter > VERDICT_DELTA_THRESHOLD and best_filter >= best_sizing:
            return EntryVerdict.ENTRY_FILTER_TOO_WEAK
        if best_sizing > VERDICT_DELTA_THRESHOLD and best_sizing > best_filter:
            return EntryVerdict.ENTRY_SIZING_SUBOPTIMAL
        if best_any < -VERDICT_DELTA_THRESHOLD and worst_any < 0:
            return EntryVerdict.ENTRY_FILTER_TOO_STRICT
        return EntryVerdict.ENTRY_LOGIC_APPROXIMATELY_OK

    def _build_recommendations(
        self,
        verdict: EntryVerdict,
        scenarios: list[ScenarioResult],
        buys: list[EntryBuyRecord],
    ) -> list[EntryRecommendation]:
        best = max(scenarios, key=lambda s: s.hypothetical_total_pnl)
        worst_score_bucket = min(
            self._aggregate_buckets(buys, lambda b: _score_bucket(b.score)),
            key=lambda b: b.total_pnl,
        )

        if verdict == EntryVerdict.ENTRY_FILTER_TOO_WEAK:
            return [
                EntryRecommendation(
                    risk_level=RecommendationRisk.MEDIUM,
                    title=f"Revizuire filtru intrare — {best.label}",
                    description=(
                        f"Scenariul '{best.label}' ar fi adăugat ${best.delta_vs_baseline:,.2f} "
                        f"față de baseline (${best.hypothetical_total_pnl:,.2f} total). "
                        "Evaluați manual dacă pragul de scor merită ridicat."
                    ),
                ),
                EntryRecommendation(
                    risk_level=RecommendationRisk.LOW,
                    title=f"Audit bucket scor {worst_score_bucket.bucket}",
                    description=(
                        f"Bucket-ul {worst_score_bucket.bucket} contribuie "
                        f"${worst_score_bucket.total_pnl:,.2f} ({worst_score_bucket.buy_count} intrări). "
                        "Identificați pattern-uri comune în reason/signal."
                    ),
                ),
                EntryRecommendation(
                    risk_level=RecommendationRisk.HIGHER,
                    title="Backtest filtru pe date out-of-sample",
                    description=(
                        "Nu implementați filtre noi fără backtest independent — "
                        "contrafactualul folosește perfect hindsight."
                    ),
                ),
            ]
        if verdict == EntryVerdict.ENTRY_SIZING_SUBOPTIMAL:
            return [
                EntryRecommendation(
                    risk_level=RecommendationRisk.MEDIUM,
                    title=f"Revizuire sizing — {best.label}",
                    description=(
                        f"Sizing contrafactual '{best.label}' delta ${best.delta_vs_baseline:+,.2f}. "
                        "Verificați dacă alocarea pe scor ar îmbunătăți risk-adjusted return."
                    ),
                ),
                EntryRecommendation(
                    risk_level=RecommendationRisk.LOW,
                    title="Mapare scor → notional",
                    description=(
                        "Documentați manual relația scor-invested actuală vs scenariul "
                        "proporțional pentru a detecta inconsistențe."
                    ),
                ),
                EntryRecommendation(
                    risk_level=RecommendationRisk.HIGHER,
                    title="Simulare lichiditate la double-size",
                    description=(
                        "Double-size pe scor 100+ crește expunerea — verificați impactul "
                        "pe cash disponibil înainte de orice schimbare."
                    ),
                ),
            ]
        if verdict == EntryVerdict.ENTRY_FILTER_TOO_STRICT:
            return [
                EntryRecommendation(
                    risk_level=RecommendationRisk.LOW,
                    title="Filtru actual posibil prea strict",
                    description=(
                        "Toate scenariile contrafactuale reduc PnL — filtrele actuale "
                        "par a exclude intrări profitabile retrospectiv."
                    ),
                ),
                EntryRecommendation(
                    risk_level=RecommendationRisk.MEDIUM,
                    title="Relaxare graduală — doar analiză",
                    description=(
                        f"Cel mai puțin dăunător scenariu: {best.label} "
                        f"(delta ${best.delta_vs_baseline:+,.2f})."
                    ),
                ),
                EntryRecommendation(
                    risk_level=RecommendationRisk.LOW,
                    title="Monitorizare fără modificare",
                    description="Păstrați regulile actuale; re-rulați analiza după 20+ tranzacții noi.",
                ),
            ]
        return [
            EntryRecommendation(
                risk_level=RecommendationRisk.LOW,
                title="Logică intrare aproximativ OK",
                description=(
                    f"Baseline ${sum(b.total_pnl for b in buys):,.2f} — "
                    f"niciun scenariu nu depășește ${VERDICT_DELTA_THRESHOLD:,.0f} delta. "
                    "Păstrați regulile actuale."
                ),
            ),
            EntryRecommendation(
                risk_level=RecommendationRisk.LOW,
                title="Segmentare pe regiune/scor",
                description=(
                    "Verificați dacă US vs Europe vs UK au profile diferite în "
                    "tabelele PnL by bucket."
                ),
            ),
            EntryRecommendation(
                risk_level=RecommendationRisk.MEDIUM,
                title="Focus pe outliers",
                description=(
                    f"Cel mai bun scenariu: {best.label} (+${best.delta_vs_baseline:,.2f}); "
                    f"cel mai slab: {min(scenarios, key=lambda s: s.hypothetical_total_pnl).label}. "
                    "Review manual pe cazuri extreme."
                ),
            ),
        ]
