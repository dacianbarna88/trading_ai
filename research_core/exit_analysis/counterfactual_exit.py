"""
Counterfactual exit analyzer — Phase VII Sprint A2

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

For each closed SELL, simulates alternative exits at +1/+3/+5/+10/+20 trading days
using Yahoo Finance historical closes.
"""

from __future__ import annotations

import csv
import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd
import yfinance as yf

from research_core.exit_analysis.exit_analysis_report import (
    BucketDelta,
    ClosedSellAnalysis,
    ExitCounterfactualReport,
    ExitRecommendation,
    ExitVerdict,
    HorizonAggregate,
    HorizonCounterfactual,
    HORIZONS,
    RankedExit,
    RecommendationRisk,
)

logger = logging.getLogger(__name__)

MIN_SHARES = 1e-9
PRIMARY_HORIZON = 5
VERDICT_MEDIAN_THRESHOLD_PCT = 0.5
VERDICT_TOTAL_DELTA_THRESHOLD = 50.0


@dataclass
class _FifoLot:
    shares: float
    cost_per_share: float
    buy_dt: datetime


@dataclass
class _ClosedSell:
    ticker: str
    sell_dt: datetime
    buy_dt: datetime
    avg_cost: float
    sell_price: float
    shares: float
    execution_pnl: float
    exit_category: str
    region: str
    signal: str
    reason: str
    timestamp: str


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
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _region_for_ticker(ticker: str) -> str:
    upper = ticker.upper()
    if upper.endswith(".L"):
        return "UK"
    if any(
        upper.endswith(suffix)
        for suffix in (".DE", ".PA", ".AS", ".MI", ".SW", ".HE", ".ST")
    ):
        return "Europe"
    return "US"


def _classify_exit_category(reason: str, signal: str) -> str:
    reason_u = (reason or "").upper()
    signal_u = (signal or "").upper()
    if "STOP" in reason_u and "LOSS" in reason_u:
        return "STOP_LOSS"
    if "TAKE" in reason_u and "PROFIT" in reason_u:
        return "TAKE_PROFIT"
    if signal_u == "STRONG BUY":
        return "STRONG_BUY_EXIT"
    if signal_u == "WAIT":
        return "WAIT_EXIT"
    return "OTHER"


def _flatten_yf_close(data: pd.DataFrame) -> pd.Series:
    if data.empty:
        return pd.Series(dtype=float)
    if isinstance(data.columns, pd.MultiIndex):
        data = data.copy()
        data.columns = data.columns.droplevel(1)
    close = data["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close.index = pd.to_datetime(close.index).tz_localize(None)
    close = close.sort_index()
    return close[close.apply(lambda v: isinstance(v, (int, float)) and math.isfinite(float(v)))]


class CounterfactualExitAnalyzer:
    def __init__(
        self,
        portfolio_csv: Path | str = "portfolio.csv",
        primary_horizon: int = PRIMARY_HORIZON,
    ) -> None:
        self._portfolio_csv = Path(portfolio_csv)
        self._primary_horizon = primary_horizon
        self._price_cache: dict[str, pd.Series] = {}

    def analyze(self) -> ExitCounterfactualReport:
        rows = self._read_csv(self._portfolio_csv)
        sells = self._fifo_closed_sells(rows)
        self._prefetch_prices(sells)

        analyses: list[ClosedSellAnalysis] = []
        for sell in sells:
            analyses.append(self._analyze_sell(sell))

        with_data = [a for a in analyses if a.price_fetch_ok]
        horizon_aggs = [self._aggregate_horizon(analyses, h) for h in HORIZONS]
        by_reason = self._bucket_breakdown(analyses, lambda a: a.exit_category)
        by_region = self._bucket_breakdown(analyses, lambda a: a.region)
        by_ticker = self._bucket_breakdown(analyses, lambda a: a.ticker)
        top_left, top_protected = self._rank_exits(analyses)
        verdict = self._compute_verdict(horizon_aggs)
        recommendations = self._build_recommendations(verdict, horizon_aggs, by_reason)

        return ExitCounterfactualReport(
            verdict=verdict,
            sells_analyzed=len(analyses),
            sells_with_price_data=len(with_data),
            horizon_aggregates=horizon_aggs,
            by_exit_reason=by_reason,
            by_region=by_region,
            by_ticker=by_ticker,
            top_left_money_on_table=top_left,
            top_protected_capital=top_protected,
            sells=analyses,
            recommendations=recommendations,
            primary_horizon_days=self._primary_horizon,
        )

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        if not path.is_file():
            return []
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            return list(csv.DictReader(handle))

    def _fifo_closed_sells(self, rows: list[dict[str, str]]) -> list[_ClosedSell]:
        parsed: list[tuple[datetime, dict[str, str]]] = []
        for row in rows:
            dt = _parse_dt(row.get("Date", ""))
            if dt is None:
                continue
            parsed.append((dt, row))
        parsed.sort(key=lambda x: x[0])

        lots: dict[str, list[_FifoLot]] = defaultdict(list)
        closed: list[_ClosedSell] = []

        for dt, row in parsed:
            action = row.get("Action", "").upper()
            ticker = row.get("Ticker", "").strip()
            if not ticker or ticker == "CASH":
                continue
            price = _safe_float(row.get("Price"))
            shares = _safe_float(row.get("Shares"))
            reason = row.get("Reason", "")
            signal = row.get("Signal", "")

            if action == "BUY":
                lots[ticker].append(_FifoLot(shares=shares, cost_per_share=price, buy_dt=dt))
            elif action == "SELL":
                remaining = shares
                exec_pnl = 0.0
                weighted_buy_ts = 0.0
                weighted_cost = 0.0
                sold = 0.0
                while remaining > MIN_SHARES and lots[ticker]:
                    lot = lots[ticker][0]
                    take = min(remaining, lot.shares)
                    exec_pnl += (price - lot.cost_per_share) * take
                    weighted_buy_ts += lot.buy_dt.timestamp() * take
                    weighted_cost += lot.cost_per_share * take
                    sold += take
                    lot.shares -= take
                    remaining -= take
                    if lot.shares <= MIN_SHARES:
                        lots[ticker].pop(0)

                if sold <= MIN_SHARES:
                    continue

                avg_cost = weighted_cost / sold
                avg_buy_dt = datetime.fromtimestamp(weighted_buy_ts / sold)
                closed.append(
                    _ClosedSell(
                        ticker=ticker,
                        sell_dt=dt,
                        buy_dt=avg_buy_dt,
                        avg_cost=avg_cost,
                        sell_price=price,
                        shares=shares,
                        execution_pnl=exec_pnl,
                        exit_category=_classify_exit_category(reason, signal),
                        region=_region_for_ticker(ticker),
                        signal=signal or "",
                        reason=reason or "",
                        timestamp=row.get("Date", ""),
                    )
                )
        return closed

    def _prefetch_prices(self, sells: list[_ClosedSell]) -> None:
        if not sells:
            return
        min_dt = min(s.buy_dt for s in sells) - timedelta(days=5)
        max_dt = max(s.sell_dt for s in sells) + timedelta(days=45)
        tickers = sorted({s.ticker for s in sells})
        for ticker in tickers:
            try:
                data = yf.download(
                    ticker,
                    start=min_dt.strftime("%Y-%m-%d"),
                    end=(max_dt + timedelta(days=1)).strftime("%Y-%m-%d"),
                    auto_adjust=False,
                    progress=False,
                )
                series = _flatten_yf_close(data)
                self._price_cache[ticker] = series
                if series.empty:
                    logger.warning("No price history for %s", ticker)
            except Exception as exc:
                logger.warning("Price fetch failed for %s: %s", ticker, exc)
                self._price_cache[ticker] = pd.Series(dtype=float)

    def _nth_trading_day_close(
        self,
        series: pd.Series,
        after_dt: datetime,
        n: int,
    ) -> tuple[float | None, datetime | None, bool]:
        if series.empty:
            return None, None, False
        future = series[series.index > pd.Timestamp(after_dt)]
        if future.empty:
            return None, None, False
        if len(future) >= n:
            idx = future.index[n - 1]
            price = float(future.iloc[n - 1])
            if not math.isfinite(price):
                return None, None, False
            return price, idx.to_pydatetime(), True
        idx = future.index[-1]
        price = float(future.iloc[-1])
        if not math.isfinite(price):
            return None, None, False
        return price, idx.to_pydatetime(), False

    def _analyze_sell(self, sell: _ClosedSell) -> ClosedSellAnalysis:
        series = self._price_cache.get(sell.ticker, pd.Series(dtype=float))
        price_ok = not series.empty
        counterfactuals: list[HorizonCounterfactual] = []

        for horizon in HORIZONS:
            exit_price, exit_dt, complete = self._nth_trading_day_close(
                series, sell.sell_dt, horizon
            )
            if exit_price is None or exit_dt is None:
                counterfactuals.append(
                    HorizonCounterfactual(
                        horizon_days=horizon,
                        exit_date="",
                        exit_price=sell.sell_price,
                        counterfactual_pnl=sell.execution_pnl,
                        delta_vs_actual=0.0,
                        data_complete=False,
                    )
                )
                continue

            cf_pnl = (exit_price - sell.avg_cost) * sell.shares
            delta = cf_pnl - sell.execution_pnl
            counterfactuals.append(
                HorizonCounterfactual(
                    horizon_days=horizon,
                    exit_date=exit_dt.strftime("%Y-%m-%d"),
                    exit_price=exit_price,
                    counterfactual_pnl=cf_pnl,
                    delta_vs_actual=delta,
                    data_complete=complete,
                )
            )

        return ClosedSellAnalysis(
            ticker=sell.ticker,
            region=sell.region,
            exit_category=sell.exit_category,
            signal=sell.signal,
            reason=sell.reason,
            buy_date=sell.buy_dt.strftime("%Y-%m-%d"),
            sell_date=sell.timestamp,
            buy_price=sell.avg_cost,
            sell_price=sell.sell_price,
            shares=sell.shares,
            actual_execution_pnl=sell.execution_pnl,
            counterfactuals=counterfactuals,
            price_fetch_ok=price_ok,
        )

    def _delta_at_horizon(self, sell: ClosedSellAnalysis, horizon: int) -> float | None:
        for cf in sell.counterfactuals:
            if cf.horizon_days == horizon and cf.data_complete:
                if math.isfinite(cf.delta_vs_actual):
                    return cf.delta_vs_actual
        for cf in sell.counterfactuals:
            if cf.horizon_days == horizon and math.isfinite(cf.delta_vs_actual):
                return cf.delta_vs_actual
        return None

    def _extra_return_pct(self, sell: ClosedSellAnalysis, horizon: int) -> float | None:
        cost_basis = sell.buy_price * sell.shares
        if cost_basis <= 0:
            return None
        delta = self._delta_at_horizon(sell, horizon)
        if delta is None:
            return None
        return (delta / cost_basis) * 100.0

    def _aggregate_horizon(
        self,
        analyses: list[ClosedSellAnalysis],
        horizon: int,
    ) -> HorizonAggregate:
        deltas: list[float] = []
        returns: list[float] = []
        improved = 0
        worse = 0
        for sell in analyses:
            delta = self._delta_at_horizon(sell, horizon)
            if delta is None:
                continue
            deltas.append(delta)
            ret = self._extra_return_pct(sell, horizon)
            if ret is not None and math.isfinite(ret):
                returns.append(ret)
            if delta > 0.01:
                improved += 1
            elif delta < -0.01:
                worse += 1

        deltas = [d for d in deltas if math.isfinite(d)]
        returns = [r for r in returns if math.isfinite(r)]
        count = len(deltas)
        total = sum(deltas) if deltas else 0.0
        avg_ret = sum(returns) / len(returns) if returns else 0.0
        med_ret = median(returns) if returns else 0.0
        pct_imp = (improved / count * 100.0) if count else 0.0
        pct_worse = (worse / count * 100.0) if count else 0.0

        return HorizonAggregate(
            horizon_days=horizon,
            total_extra_profit=total,
            avg_extra_return_pct=avg_ret,
            median_extra_return_pct=med_ret,
            pct_improved=pct_imp,
            pct_worse=pct_worse,
            analyzed_count=count,
        )

    def _bucket_breakdown(
        self,
        analyses: list[ClosedSellAnalysis],
        key_fn,
    ) -> list[BucketDelta]:
        buckets: dict[tuple[str, int], list[float]] = defaultdict(list)
        for sell in analyses:
            bucket = key_fn(sell)
            for horizon in HORIZONS:
                delta = self._delta_at_horizon(sell, horizon)
                if delta is not None and math.isfinite(delta):
                    buckets[(bucket, horizon)].append(delta)

        out: list[BucketDelta] = []
        for (bucket, horizon), deltas in sorted(buckets.items()):
            total = sum(deltas)
            count = len(deltas)
            avg = total / count if count else 0.0
            out.append(
                BucketDelta(
                    bucket=bucket,
                    horizon_days=horizon,
                    total_delta=total,
                    trade_count=count,
                    avg_delta=avg,
                )
            )
        return out

    def _rank_exits(
        self,
        analyses: list[ClosedSellAnalysis],
    ) -> tuple[list[RankedExit], list[RankedExit]]:
        ranked: list[RankedExit] = []
        for sell in analyses:
            cf = next(
                (c for c in sell.counterfactuals if c.horizon_days == self._primary_horizon),
                None,
            )
            if cf is None or not math.isfinite(cf.delta_vs_actual):
                continue
            ranked.append(
                RankedExit(
                    ticker=sell.ticker,
                    sell_date=sell.sell_date,
                    exit_category=sell.exit_category,
                    actual_pnl=sell.actual_execution_pnl,
                    delta_at_5d=cf.delta_vs_actual,
                    sell_price=sell.sell_price,
                    price_at_5d=cf.exit_price,
                    reason=sell.reason,
                )
            )

        finite = [r for r in ranked if math.isfinite(r.delta_at_5d)]
        left = sorted(finite, key=lambda r: r.delta_at_5d, reverse=True)[:10]
        protected = sorted(finite, key=lambda r: r.delta_at_5d)[:10]
        return left, protected

    def _compute_verdict(self, horizon_aggs: list[HorizonAggregate]) -> ExitVerdict:
        primary = next(
            (h for h in horizon_aggs if h.horizon_days == self._primary_horizon),
            None,
        )
        if primary is None or primary.analyzed_count == 0:
            return ExitVerdict.EXITS_APPROXIMATELY_OPTIMAL

        med = primary.median_extra_return_pct
        total = primary.total_extra_profit
        pct_imp = primary.pct_improved
        pct_worse = primary.pct_worse

        # Portfolio-level dollars + per-trade median must agree for a strong verdict.
        if total > VERDICT_TOTAL_DELTA_THRESHOLD and med > VERDICT_MEDIAN_THRESHOLD_PCT:
            return ExitVerdict.EXITS_TOO_EARLY
        if total < -VERDICT_TOTAL_DELTA_THRESHOLD and med < -VERDICT_MEDIAN_THRESHOLD_PCT:
            return ExitVerdict.EXITS_TOO_LATE
        # Per-trade skew without aggregate confirmation → mixed / near-optimal.
        if med > VERDICT_MEDIAN_THRESHOLD_PCT and pct_imp >= 55.0 and total > 0:
            return ExitVerdict.EXITS_TOO_EARLY
        if med < -VERDICT_MEDIAN_THRESHOLD_PCT and pct_worse >= 55.0 and total < 0:
            return ExitVerdict.EXITS_TOO_LATE
        return ExitVerdict.EXITS_APPROXIMATELY_OPTIMAL

    def _build_recommendations(
        self,
        verdict: ExitVerdict,
        horizon_aggs: list[HorizonAggregate],
        by_reason: list[BucketDelta],
    ) -> list[ExitRecommendation]:
        primary = next(
            (h for h in horizon_aggs if h.horizon_days == self._primary_horizon),
            None,
        )
        pct_imp = primary.pct_improved if primary else 0.0
        reason_rows = [
            b
            for b in by_reason
            if b.horizon_days == self._primary_horizon and math.isfinite(b.total_delta)
        ]
        worst_reason = sorted(reason_rows, key=lambda b: b.total_delta, reverse=True)
        top_reason = worst_reason[0].bucket if worst_reason else "OTHER"

        if verdict == ExitVerdict.EXITS_TOO_EARLY:
            recs = [
                ExitRecommendation(
                    risk_level=RecommendationRisk.MEDIUM,
                    title="Revizuire praguri TAKE PROFIT",
                    description=(
                        f"La +{self._primary_horizon} zile, {pct_imp:.0f}% din ieșiri ar fi "
                        f"fost mai bune dacă s-ar fi așteptat. Verificați dacă TP este prea "
                        f"tight pentru regiunea/tickerul dominant."
                    ),
                ),
                ExitRecommendation(
                    risk_level=RecommendationRisk.LOW,
                    title=f"Audit categorie {top_reason}",
                    description=(
                        f"Categoria {top_reason} contribuie cel mai mult la profitul "
                        "contrafactual pierdut. Revizuiți manual regulile de ieșire pentru "
                        "acest motiv."
                    ),
                ),
                ExitRecommendation(
                    risk_level=RecommendationRisk.HIGHER,
                    title="Trailing stop vs exit fix",
                    description=(
                        "Simulați offline un trailing stop pe aceleași tranzacții înainte "
                        "de orice modificare live — datele sugerează ieșiri premature."
                    ),
                ),
            ]
        elif verdict == ExitVerdict.EXITS_TOO_LATE:
            recs = [
                ExitRecommendation(
                    risk_level=RecommendationRisk.MEDIUM,
                    title="Întărire stop-loss",
                    description=(
                        "Contrafactualul arată că așteptarea după SELL ar fi redus PnL — "
                        "ieșirile actuale protejează capital. Verificați dacă SL este "
                        "suficient de rapid."
                    ),
                ),
                ExitRecommendation(
                    risk_level=RecommendationRisk.LOW,
                    title=f"Validare {top_reason}",
                    description=(
                        f"Categoria {top_reason} are delta negativă la +{self._primary_horizon} "
                        "zile — exit-ul actual pare superior așteptării."
                    ),
                ),
                ExitRecommendation(
                    risk_level=RecommendationRisk.LOW,
                    title="Păstrare discipline exit",
                    description=(
                        "Nu extindeți holding-ul pe baza acestui raport fără backtest "
                        "independent — ieșirile curente par aproximativ corecte sau tardive."
                    ),
                ),
            ]
        else:
            recs = [
                ExitRecommendation(
                    risk_level=RecommendationRisk.LOW,
                    title="Monitorizare continuă",
                    description=(
                        f"Delta mediană la +{self._primary_horizon} zile este aproape de zero — "
                        "păstrați regulile actuale și re-rulați analiza lunar."
                    ),
                ),
                ExitRecommendation(
                    risk_level=RecommendationRisk.LOW,
                    title="Segmentare pe regiune",
                    description=(
                        "Verificați dacă US vs Europe vs UK au profile contrafactuale "
                        "diferite înainte de ajustări regionale."
                    ),
                ),
                ExitRecommendation(
                    risk_level=RecommendationRisk.MEDIUM,
                    title="Focus pe outliers",
                    description=(
                        "Top 10 ieșiri cu delta extremă merită review manual — agregatul "
                        "este optim, dar cazuri individuale pot necesita reguli specifice."
                    ),
                ),
            ]
        return recs
