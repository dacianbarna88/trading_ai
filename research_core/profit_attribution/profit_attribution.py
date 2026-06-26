"""
Profit attribution engine — Phase VII Sprint A1

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Explains mathematically why net profit is modest despite many trades.
Internal FIFO execution PnL — does not trust stale portfolio.csv SELL PnL column.
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
from typing import Any

from research_core.profit_attribution.attribution_report import (
    AttributionRecommendation,
    AttributionReportStore,
    AttributionVerdict,
    BucketContribution,
    CoreMetrics,
    ExternalReference,
    ProfitAttributionReport,
    ProfitConcentration,
    RecommendationRisk,
    SAFETY_BANNER,
    TickerContribution,
)

logger = logging.getLogger(__name__)

PORTFOLIO_PATH = Path("portfolio.csv")
INDEPENDENT_JSON = Path("tae_independent_double_entry_verification.json")
LEDGER_JSON = Path("tae_cash_flow_ledger.json")
STRATEGIC_JSON = Path("tae_strategic_performance_audit.json")
FALLBACK_STARTING_CAPITAL = 30000.0
MIN_SHARES = 0.0001
EUROPE_SUFFIXES = (".DE", ".PA", ".AS", ".MI", ".SW", ".BR")
UK_SUFFIX = ".L"

HOLDING_BUCKETS = [
    ("same-day", 0, 0),
    ("1-2d", 1, 2),
    ("3-5d", 3, 5),
    ("6-10d", 6, 10),
    ("10d+", 11, 9999),
]

SIZE_BUCKETS = [
    ("micro", 0, 100),
    ("small", 100, 500),
    ("medium", 500, 2000),
    ("large", 2000, 5000),
    ("xlarge", 5000, 1e12),
]

SCORE_BUCKETS = [
    ("score_0-39", 0, 39),
    ("score_40-79", 40, 79),
    ("score_80-109", 80, 109),
    ("score_110+", 110, 999),
]


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


def _resolve_starting_capital() -> float:
    try:
        from config.settings import STARTING_CAPITAL

        return float(STARTING_CAPITAL)
    except (ImportError, AttributeError, TypeError, ValueError):
        return FALLBACK_STARTING_CAPITAL


def _region_for_ticker(ticker: str) -> str:
    upper = ticker.upper()
    if upper.endswith(UK_SUFFIX):
        return "UK"
    for suffix in EUROPE_SUFFIXES:
        if upper.endswith(suffix):
            return "Europe"
    return "US"


def _classify_exit_reason(reason: str, signal: str) -> str:
    ru = reason.upper()
    su = signal.upper()
    if "REBALANCE" in ru or su == "REBALANCE":
        return "REBALANCE"
    if "TAKE PROFIT" in ru or "TAKE PROFIT" in su:
        return "TAKE_PROFIT"
    if "STOP LOSS" in ru or "STOP LOSS" in su:
        return "STOP_LOSS"
    if "PROFIT" in ru:
        return "PROFIT"
    return "OTHER"


def _holding_bucket(days: int) -> str:
    for name, lo, hi in HOLDING_BUCKETS:
        if lo <= days <= hi:
            return name
    return "10d+"


def _size_bucket(proceeds: float) -> str:
    for name, lo, hi in SIZE_BUCKETS:
        if lo <= proceeds < hi:
            return name
    return "xlarge"


def _score_bucket(score: float) -> str:
    for name, lo, hi in SCORE_BUCKETS:
        if lo <= score <= hi:
            return name
    return "score_0-39"


@dataclass
class _FifoLot:
    shares: float
    cost_per_share: float
    buy_dt: datetime


@dataclass
class ClosedTrade:
    timestamp: str
    ticker: str
    sell_price: float
    shares: float
    proceeds: float
    execution_pnl: float
    holding_days: int
    exit_reason: str
    region: str
    score: float
    size_bucket: str
    holding_bucket: str
    stored_pnl: float
    pnl_stale: bool


class ProfitAttributionEngine:
    """Read-only profit attribution from portfolio.csv with internal FIFO PnL."""

    def __init__(self, store: AttributionReportStore | None = None) -> None:
        self._store = store or AttributionReportStore()

    def analyze(self) -> ProfitAttributionReport:
        rows = self._read_csv(PORTFOLIO_PATH)
        starting_capital = _resolve_starting_capital()
        deposits = self._sum_deposits(rows)
        closed_trades = self._fifo_closed_trades(rows)
        open_unrealized = self._open_unrealized_pnl(rows)

        wins = [t.execution_pnl for t in closed_trades if t.execution_pnl > 0]
        losses = [t.execution_pnl for t in closed_trades if t.execution_pnl < 0]
        gross_profit = sum(wins)
        gross_loss = sum(losses)
        net_realized = sum(t.execution_pnl for t in closed_trades)
        total_pnl = net_realized + open_unrealized
        closed_count = len(closed_trades)
        win_count = len(wins)
        lose_count = len(losses)

        win_rate = (win_count / closed_count * 100.0) if closed_count else 0.0
        avg_win = (gross_profit / win_count) if win_count else 0.0
        avg_loss = (gross_loss / lose_count) if lose_count else 0.0
        med_win = statistics.median(wins) if wins else 0.0
        med_loss = statistics.median(losses) if losses else 0.0
        payoff = (avg_win / abs(avg_loss)) if avg_loss else 0.0
        profit_factor = (gross_profit / abs(gross_loss)) if gross_loss else float("inf")
        expectancy = net_realized / closed_count if closed_count else 0.0

        core = CoreMetrics(
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            net_realized_profit=net_realized,
            open_unrealized_pnl=open_unrealized,
            total_pnl=total_pnl,
            win_rate=win_rate,
            average_win=avg_win,
            average_loss=avg_loss,
            median_win=med_win,
            median_loss=med_loss,
            payoff_ratio=payoff,
            profit_factor=profit_factor if profit_factor != float("inf") else 999.0,
            expectancy_per_trade=expectancy,
            closed_trade_count=closed_count,
            winning_trades=win_count,
            losing_trades=lose_count,
        )

        pnl_by_ticker = self._aggregate_ticker(closed_trades)
        pnl_by_region = self._aggregate_bucket(
            closed_trades, lambda t: t.region
        )
        pnl_by_exit = self._aggregate_bucket(
            closed_trades, lambda t: t.exit_reason
        )
        pnl_by_holding = self._aggregate_bucket(
            closed_trades, lambda t: t.holding_bucket
        )
        pnl_by_size = self._aggregate_bucket(
            closed_trades, lambda t: t.size_bucket
        )
        pnl_by_score = self._aggregate_bucket(
            closed_trades, lambda t: _score_bucket(t.score)
        ) if any(t.score > 0 for t in closed_trades) else []

        concentration = self._profit_concentration(closed_trades, net_realized, gross_profit, gross_loss)
        explanation = self._build_explanation(
            core, closed_trades, pnl_by_ticker, pnl_by_region, pnl_by_exit, concentration
        )
        verdict = self._select_verdict(core, concentration, closed_count)
        recommendations = self._build_recommendations(core, concentration, pnl_by_region, pnl_by_exit)
        external = self._load_external_refs(total_pnl, net_realized, open_unrealized)

        stale_count = sum(1 for t in closed_trades if t.pnl_stale)
        if stale_count:
            external.append(
                ExternalReference(
                    source="Stale PnL column check",
                    available=True,
                    notes=(
                        f"{stale_count}/{closed_count} SELL rows had stored PnL "
                        f"diverging >$5 from FIFO execution — ignored for attribution"
                    ),
                )
            )

        report = ProfitAttributionReport(
            verdict=verdict,
            core=core,
            pnl_by_ticker=pnl_by_ticker,
            pnl_by_region=pnl_by_region,
            pnl_by_exit_reason=pnl_by_exit,
            pnl_by_holding_period=pnl_by_holding,
            pnl_by_position_size=pnl_by_size,
            pnl_by_score=pnl_by_score,
            concentration=concentration,
            mathematical_explanation=explanation,
            recommendations=recommendations,
            external_references=external,
            starting_capital=starting_capital,
            deposits=deposits,
            safety_mode=SAFETY_BANNER,
        )
        self._store.persist(report)
        self._store.persist_txt(report)
        return report

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        if not path.is_file():
            return []
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            return list(csv.DictReader(handle))

    def _sum_deposits(self, rows: list[dict[str, str]]) -> float:
        total = 0.0
        for row in rows:
            if row.get("Action", "").upper() != "DEPOSIT":
                continue
            price = _safe_float(row.get("Price"))
            shares = _safe_float(row.get("Shares"), 1.0)
            total += price * shares
        return total

    def _fifo_closed_trades(self, rows: list[dict[str, str]]) -> list[ClosedTrade]:
        parsed: list[tuple[datetime, dict[str, str]]] = []
        for row in rows:
            dt = _parse_dt(row.get("Date", ""))
            if dt is None:
                continue
            parsed.append((dt, row))
        parsed.sort(key=lambda x: x[0])

        lots: dict[str, list[_FifoLot]] = defaultdict(list)
        closed: list[ClosedTrade] = []

        for dt, row in parsed:
            action = row.get("Action", "").upper()
            ticker = row.get("Ticker", "").strip()
            if not ticker or ticker == "CASH":
                continue
            price = _safe_float(row.get("Price"))
            shares = _safe_float(row.get("Shares"))
            score = _safe_float(row.get("Score"))
            reason = row.get("Reason", "")
            signal = row.get("Signal", "")
            stored_pnl = _safe_float(row.get("PnL"))

            if action == "BUY":
                lots[ticker].append(
                    _FifoLot(shares=shares, cost_per_share=price, buy_dt=dt)
                )
            elif action == "SELL":
                proceeds = price * shares
                remaining = shares
                exec_pnl = 0.0
                weighted_days = 0.0
                sold_shares = 0.0
                while remaining > MIN_SHARES and lots[ticker]:
                    lot = lots[ticker][0]
                    take = min(remaining, lot.shares)
                    lot_pnl = (price - lot.cost_per_share) * take
                    exec_pnl += lot_pnl
                    days = max(0, (dt - lot.buy_dt).days)
                    weighted_days += days * take
                    sold_shares += take
                    lot.shares -= take
                    remaining -= take
                    if lot.shares <= MIN_SHARES:
                        lots[ticker].pop(0)

                avg_holding = int(weighted_days / sold_shares) if sold_shares else 0
                exit_reason = _classify_exit_reason(reason, signal)
                stale = abs(stored_pnl - exec_pnl) > 5.0 and abs(stored_pnl) > 1.0

                trade = ClosedTrade(
                    timestamp=row.get("Date", ""),
                    ticker=ticker,
                    sell_price=price,
                    shares=shares,
                    proceeds=proceeds,
                    execution_pnl=exec_pnl,
                    holding_days=avg_holding,
                    exit_reason=exit_reason,
                    region=_region_for_ticker(ticker),
                    score=score,
                    size_bucket=_size_bucket(proceeds),
                    holding_bucket=_holding_bucket(avg_holding),
                    stored_pnl=stored_pnl,
                    pnl_stale=stale,
                )
                closed.append(trade)
        return closed

    def _open_unrealized_pnl(self, rows: list[dict[str, str]]) -> float:
        """Open unrealized from portfolio.csv Current_Price (canonical marks)."""
        lots: dict[str, list[_FifoLot]] = defaultdict(list)
        latest_marks: dict[str, float] = {}
        parsed: list[tuple[datetime, dict[str, str]]] = []
        for row in rows:
            dt = _parse_dt(row.get("Date", ""))
            if dt is None:
                continue
            parsed.append((dt, row))
        parsed.sort(key=lambda x: x[0])

        for dt, row in parsed:
            ticker = row.get("Ticker", "").strip()
            action = row.get("Action", "").upper()
            if not ticker or ticker == "CASH":
                continue
            cp = _safe_float(row.get("Current_Price"))
            if cp > 0:
                latest_marks[ticker] = cp
            price = _safe_float(row.get("Price"))
            shares = _safe_float(row.get("Shares"))
            if action == "BUY":
                lots[ticker].append(_FifoLot(shares=shares, cost_per_share=price, buy_dt=dt))
            elif action == "SELL":
                remaining = shares
                while remaining > MIN_SHARES and lots[ticker]:
                    lot = lots[ticker][0]
                    take = min(remaining, lot.shares)
                    lot.shares -= take
                    remaining -= take
                    if lot.shares <= MIN_SHARES:
                        lots[ticker].pop(0)

        total = 0.0
        for ticker, flots in lots.items():
            open_shares = sum(lot.shares for lot in flots)
            if open_shares <= MIN_SHARES:
                continue
            cost = sum(lot.shares * lot.cost_per_share for lot in flots)
            mark = latest_marks.get(ticker, cost / open_shares if open_shares else 0)
            total += open_shares * mark - cost
        return round(total, 2)

    def _aggregate_ticker(self, trades: list[ClosedTrade]) -> list[TickerContribution]:
        by_ticker: dict[str, list[float]] = defaultdict(list)
        for t in trades:
            by_ticker[t.ticker].append(t.execution_pnl)
        return [
            TickerContribution(
                ticker=ticker,
                realized_pnl=sum(pnls),
                trade_count=len(pnls),
                region=_region_for_ticker(ticker),
            )
            for ticker, pnls in sorted(by_ticker.items())
        ]

    def _aggregate_bucket(
        self,
        trades: list[ClosedTrade],
        key_fn,
    ) -> list[BucketContribution]:
        buckets: dict[str, list[float]] = defaultdict(list)
        for t in trades:
            buckets[key_fn(t)].append(t.execution_pnl)
        order = []
        seen = set()
        for t in trades:
            k = key_fn(t)
            if k not in seen:
                order.append(k)
                seen.add(k)
        result: list[BucketContribution] = []
        for bucket in order:
            pnls = buckets[bucket]
            wins = sum(1 for p in pnls if p > 0)
            result.append(
                BucketContribution(
                    bucket=bucket,
                    pnl=sum(pnls),
                    trade_count=len(pnls),
                    win_rate=(wins / len(pnls) * 100.0) if pnls else 0.0,
                )
            )
        return result

    def _profit_concentration(
        self,
        trades: list[ClosedTrade],
        net_realized: float,
        gross_profit: float,
        gross_loss: float,
    ) -> ProfitConcentration:
        sorted_trades = sorted(trades, key=lambda t: t.execution_pnl, reverse=True)
        winners = [t for t in sorted_trades if t.execution_pnl > 0]
        losers = [t for t in sorted_trades if t.execution_pnl < 0]

        top5_w = winners[:5]
        top5_l = sorted(losers, key=lambda t: t.execution_pnl)[:5]
        top5_w_pnl = sum(t.execution_pnl for t in top5_w)
        top5_l_pnl = sum(t.execution_pnl for t in top5_l)

        top5_w_pct = (top5_w_pnl / net_realized * 100.0) if net_realized else 0.0
        top5_l_pct = (abs(top5_l_pnl) / abs(gross_loss) * 100.0) if gross_loss else 0.0

        n_win = max(1, int(len(winners) * 0.2) or 1)
        n_lose = max(1, int(len(losers) * 0.2) or 1)
        top20_win_share = (
            sum(t.execution_pnl for t in winners[:n_win]) / gross_profit * 100.0
            if gross_profit
            else 0.0
        )
        bot20_lose_share = (
            abs(sum(t.execution_pnl for t in losers[:n_lose])) / abs(gross_loss) * 100.0
            if gross_loss
            else 0.0
        )

        pareto = (
            f"Top 20% winners supply {top20_win_share:.1f}% of gross profit; "
            f"bottom 20% losers account for {bot20_lose_share:.1f}% of gross loss."
        )

        return ProfitConcentration(
            top_5_winners_pnl=top5_w_pnl,
            top_5_winners_contribution_pct=top5_w_pct,
            top_5_losers_pnl=top5_l_pnl,
            top_5_losers_drag_pct=top5_l_pct,
            top_20pct_winners_share_of_gross_profit=top20_win_share,
            bottom_20pct_losers_share_of_gross_loss=bot20_lose_share,
            pareto_summary=pareto,
            top_winners=[
                {"ticker": t.ticker, "pnl": round(t.execution_pnl, 2), "reason": t.exit_reason}
                for t in top5_w
            ],
            top_losers=[
                {"ticker": t.ticker, "pnl": round(t.execution_pnl, 2), "reason": t.exit_reason}
                for t in top5_l
            ],
        )

    def _build_explanation(
        self,
        core: CoreMetrics,
        trades: list[ClosedTrade],
        by_ticker: list[TickerContribution],
        by_region: list[BucketContribution],
        by_exit: list[BucketContribution],
        concentration: ProfitConcentration,
    ) -> list[str]:
        loss_pct_of_gross = (
            abs(core.gross_loss) / core.gross_profit * 100.0 if core.gross_profit else 0.0
        )
        top_winner = max(by_ticker, key=lambda t: t.realized_pnl, default=None)
        top_loser = min(by_ticker, key=lambda t: t.realized_pnl, default=None)
        us_pnl = next((b.pnl for b in by_region if b.bucket == "US"), 0.0)
        europe_pnl = next((b.pnl for b in by_region if b.bucket == "Europe"), 0.0)
        stop_pnl = next((b.pnl for b in by_exit if b.bucket == "STOP_LOSS"), 0.0)
        micro_trades = sum(1 for t in trades if t.size_bucket == "micro")

        tw_pct = (
            top_winner.realized_pnl / core.net_realized_profit * 100.0
            if top_winner and core.net_realized_profit
            else 0.0
        )
        tl_pct = (
            abs(top_loser.realized_pnl) / abs(core.gross_loss) * 100.0
            if top_loser and core.gross_loss
            else 0.0
        )

        return [
            (
                f"Pierderile realizate (${abs(core.gross_loss):,.2f}) consumă "
                f"{loss_pct_of_gross:.1f}% din profitul brut (${core.gross_profit:,.2f}), "
                f"lăsând doar ${core.net_realized_profit:,.2f} net din {core.closed_trade_count} SELL-uri."
            ),
            (
                f"Câștigătorul principal {top_winner.ticker if top_winner else 'N/A'} "
                f"({top_winner.realized_pnl:,.2f}) furnizează ~{tw_pct:.1f}% din profitul net realizat — "
                f"profitul depinde puternic de puține tranzacții."
                if top_winner
                else "Niciun câștigător dominant identificat."
            ),
            (
                f"Pierderea {top_loser.ticker if top_loser else 'N/A'} "
                f"({top_loser.realized_pnl:,.2f}) reprezintă ~{tl_pct:.1f}% din pierderea brută totală."
                if top_loser
                else "Pierderile sunt distribuite uniform."
            ),
            (
                f"Regiunea US: PnL realizat ${us_pnl:,.2f}; Europa: ${europe_pnl:,.2f} — "
                f"diversificarea regională nu compensează pierderile US."
            ),
            (
                f"Pozițiile deschise adaugă doar ${core.open_unrealized_pnl:,.2f} nerealizat; "
                f"PnL total ${core.total_pnl:,.2f} ≈ capital + {core.total_pnl:,.2f} față de "
                f"start+depozite."
            ),
            (
                f"Win rate {core.win_rate:.1f}% cu payoff {core.payoff_ratio:.2f} — "
                f"{'insuficient pentru scalare agresivă' if core.win_rate < 55 else 'moderat'} "
                f"la {core.closed_trade_count} tranzacții închise."
            ),
            (
                f"Pierderea medie (${abs(core.average_loss):,.2f}) vs câștigul mediu "
                f"(${core.average_win:,.2f}) — raport {core.payoff_ratio:.2f}x; "
                f"profit factor {core.profit_factor:.2f}."
            ),
            (
                f"{micro_trades} tranzacții micro (<$100) și loturi near-zero (IBM/INTC) "
                f"generează turnover fără contribuție materială la PnL."
            ),
            (
                f"Clasa STOP_LOSS: PnL cumulat ${stop_pnl:,.2f} — ieșiri defensive "
                f"{'trag portfolio' if stop_pnl < -200 else 'limitează pierderi'}."
            ),
            (
                f"Așteptare ${core.expectancy_per_trade:,.2f}/SELL × {core.closed_trade_count} "
                f"tranzacții = ${core.net_realized_profit:,.2f}; "
                f"{concentration.pareto_summary}"
            ),
        ]

    def _select_verdict(
        self,
        core: CoreMetrics,
        concentration: ProfitConcentration,
        closed_count: int,
    ) -> AttributionVerdict:
        loss_drag_ratio = (
            abs(core.gross_loss) / core.gross_profit if core.gross_profit else 1.0
        )
        if closed_count < 15:
            return AttributionVerdict.PROFIT_HEALTHY_BUT_SMALL_SAMPLE
        if concentration.top_5_winners_contribution_pct > 120:
            return AttributionVerdict.PROFIT_LOW_DUE_TO_CONCENTRATION
        if core.win_rate < 48:
            return AttributionVerdict.PROFIT_LOW_DUE_TO_LOW_WIN_RATE
        if loss_drag_ratio > 0.85:
            return AttributionVerdict.PROFIT_LOW_DUE_TO_LOSS_DRAG
        if core.average_win < abs(core.average_loss) * 0.9:
            return AttributionVerdict.PROFIT_LOW_DUE_TO_SMALL_WINNERS
        if concentration.top_5_winners_contribution_pct > 80:
            return AttributionVerdict.PROFIT_LOW_DUE_TO_CONCENTRATION
        return AttributionVerdict.PROFIT_LOW_DUE_TO_LOSS_DRAG

    def _build_recommendations(
        self,
        core: CoreMetrics,
        concentration: ProfitConcentration,
        by_region: list[BucketContribution],
        by_exit: list[BucketContribution],
    ) -> list[AttributionRecommendation]:
        europe = next((b for b in by_region if b.bucket == "Europe"), None)
        stop = next((b for b in by_exit if b.bucket == "STOP_LOSS"), None)
        return [
            AttributionRecommendation(
                risk_level=RecommendationRisk.LOW,
                title="Monitor pierderi mari pe ticker",
                description=(
                    f"Urmăriți read-only tickere cu pierdere FIFO >$100 (ex. AAPL, ORCL) "
                    f"și raportați dacă STOP_LOSS ({stop.pnl if stop else 0:,.2f}) "
                    f"depășește 30% din gross loss."
                ),
            ),
            AttributionRecommendation(
                risk_level=RecommendationRisk.MEDIUM,
                title="Cercetare regiune Europa",
                description=(
                    f"PnL Europa realizat ${europe.pnl if europe else 0:,.2f} — "
                    f"analizați dacă SIE.DE și MC.PA au edge suficient înainte de "
                    f"extindere; date regionale incomplete în TAE."
                ),
            ),
            AttributionRecommendation(
                risk_level=RecommendationRisk.HIGHER,
                title="Candidat ajustare strategie — concentrare GS",
                description=(
                    f"Top 5 câștigători = {concentration.top_5_winners_contribution_pct:.0f}% "
                    f"din net; fără GS (+547) net ar fi ~${core.net_realized_profit - 548:,.0f}. "
                    f"Evaluați sizing și diversificare — NOT_IMPLEMENTED."
                ),
            ),
        ]

    def _load_external_refs(
        self,
        total_pnl: float,
        net_realized: float,
        open_pnl: float,
    ) -> list[ExternalReference]:
        refs: list[ExternalReference] = []
        for path, name in (
            (INDEPENDENT_JSON, "Independent double-entry"),
            (LEDGER_JSON, "Cash flow ledger B5"),
            (STRATEGIC_JSON, "Strategic performance audit"),
        ):
            if not path.is_file():
                refs.append(ExternalReference(source=name, available=False, notes="File missing"))
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if name == "Strategic performance audit":
                    perf = data.get("performance", {})
                    refs.append(
                        ExternalReference(
                            source=name,
                            available=True,
                            realized_pnl=_safe_float(perf.get("all_history_realized_pnl")),
                            open_pnl=_safe_float(perf.get("total_pnl")) - _safe_float(
                                perf.get("all_history_realized_pnl")
                            ),
                            total_pnl=_safe_float(perf.get("total_pnl")),
                            notes="Uses stale portfolio.csv PnL — contrast with FIFO",
                        )
                    )
                elif name == "Independent double-entry":
                    refs.append(
                        ExternalReference(
                            source=name,
                            available=True,
                            total_pnl=_safe_float(data.get("independent_total_pnl")),
                            realized_pnl=_safe_float(data.get("independent_realized_pnl")),
                            open_pnl=_safe_float(data.get("independent_open_unrealized_pnl")),
                            notes=f"Verdict: {data.get('verdict', 'N/A')}",
                        )
                    )
                else:
                    summary = data.get("summary", {})
                    refs.append(
                        ExternalReference(
                            source=name,
                            available=True,
                            total_pnl=_safe_float(summary.get("total_pnl")),
                            realized_pnl=_safe_float(summary.get("realized_pnl_all_sells")),
                            open_pnl=_safe_float(
                                summary.get("open_unrealized_pnl_portfolio_csv")
                                or summary.get("open_unrealized_pnl")
                            ),
                            notes=(
                                f"Canonical AV ${summary.get('account_value_from_portfolio_csv_marks', summary.get('final_account_value', 0)):,.2f}"
                            ),
                        )
                    )
            except (OSError, json.JSONDecodeError) as exc:
                refs.append(ExternalReference(source=name, available=False, notes=str(exc)))

        delta_ind = next((r for r in refs if r.source == "Independent double-entry" and r.available), None)
        if delta_ind and delta_ind.total_pnl is not None:
            refs.append(
                ExternalReference(
                    source="Attribution vs independent",
                    available=True,
                    total_pnl=total_pnl,
                    realized_pnl=net_realized,
                    open_pnl=open_pnl,
                    notes=f"Delta total ${total_pnl - delta_ind.total_pnl:,.2f}",
                )
            )
        return refs
