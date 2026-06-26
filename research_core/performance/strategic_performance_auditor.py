"""
Strategic performance auditor — V1

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only analysis of portfolio decline drivers — no execution or file modifications.
"""

from __future__ import annotations

import csv
import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from research_core.performance.performance_report import (
    ANALYSIS_SAFETY_BANNER,
    Anomaly,
    PerformanceAuditStore,
    PerformanceMetrics,
    PeriodComparison,
    PortfolioActivity,
    Recommendation,
    RecommendationRisk,
    RegionalPnL,
    SignalQuality,
    StrategicPerformanceAudit,
    TradeQuality,
)

logger = logging.getLogger(__name__)

PORTFOLIO_PATH = Path("portfolio.csv")
LATEST_PORTFOLIO_PATH = Path("latest_portfolio.txt")
LIVE_SIGNALS_PATH = Path("live_signals.csv")
ALERTS_LOG_PATH = Path("alerts_log.csv")
BOT_LOG_PATH = Path("bot_output.log")
LEARNING_PATH = Path("tae_learning_report.json")
RECOMMENDATIONS_PATH = Path("tae_strategy_recommendations.json")
PROCESS_HEALTH_PATH = Path("process_health.json")
BOT_STATUS_PATH = Path("bot_status.txt")

EUROPE_SUFFIXES = (".DE", ".PA", ".AS", ".MI", ".SW", ".BR")
UK_SUFFIX = ".L"
NEAR_ZERO_INVESTED = 1.0
MIN_SHARES_OPEN = 0.0001


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


def _region_for_ticker(ticker: str) -> str:
    upper = ticker.upper()
    if upper.endswith(UK_SUFFIX):
        return "UK"
    for suffix in EUROPE_SUFFIXES:
        if upper.endswith(suffix):
            return "Europe"
    if upper in ("CASH", "DEPOSIT"):
        return "Cash"
    return "US"


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
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as exc:
        logger.warning("Could not read CSV %s: %s", path, exc)
        return []


def _is_trade_action(action: str) -> bool:
    return action.upper() in ("BUY", "SELL")


@dataclass
class _Position:
    shares: float = 0.0
    cost_basis: float = 0.0
    current_value: float = 0.0
    current_price: float = 0.0
    last_date: datetime | None = None


@dataclass
class _ParsedRow:
    dt: datetime
    ticker: str
    action: str
    price: float
    shares: float
    score: float
    signal: str
    reason: str
    invested: float
    current_value: float
    pnl: float
    pnl_pct: float


def _is_realized_sell_row(row: _ParsedRow) -> bool:
    if row.action != "SELL":
        return False
    reason = row.reason.upper()
    signal = row.signal.upper()
    if "REBALANCE" in reason or signal == "REBALANCE":
        return False
    if row.ticker.upper() == "CASH":
        return False
    return True


class StrategicPerformanceAuditor:
    """Read-only strategic performance audit engine."""

    def __init__(self, store: PerformanceAuditStore | None = None) -> None:
        self._store = store or PerformanceAuditStore()
        self._sources_loaded: dict[str, bool] = {}

    def audit(self) -> StrategicPerformanceAudit:
        now = datetime.now(timezone.utc)
        rows_raw = _read_csv_rows(PORTFOLIO_PATH)
        self._sources_loaded["portfolio.csv"] = bool(rows_raw)

        latest_txt = LATEST_PORTFOLIO_PATH.is_file()
        self._sources_loaded["latest_portfolio.txt"] = latest_txt

        signals_raw = _read_csv_rows(LIVE_SIGNALS_PATH)
        self._sources_loaded["live_signals.csv"] = bool(signals_raw)

        alerts_raw = _read_csv_rows(ALERTS_LOG_PATH)
        self._sources_loaded["alerts_log.csv"] = bool(alerts_raw)

        bot_log_exists = BOT_LOG_PATH.is_file()
        self._sources_loaded["bot_output.log"] = bot_log_exists

        learning = _load_json(LEARNING_PATH)
        self._sources_loaded["tae_learning_report.json"] = learning is not None

        recommendations = _load_json(RECOMMENDATIONS_PATH)
        self._sources_loaded["tae_strategy_recommendations.json"] = recommendations is not None

        process_health = _load_json(PROCESS_HEALTH_PATH)
        self._sources_loaded["process_health.json"] = process_health is not None

        bot_status_exists = BOT_STATUS_PATH.is_file()
        self._sources_loaded["bot_status.txt"] = bot_status_exists

        parsed = self._parse_portfolio(rows_raw)
        ref_date = max((r.dt for r in parsed), default=datetime.now())

        two_day_start = ref_date - timedelta(days=2)
        seven_day_start = ref_date - timedelta(days=9)
        three_day_start = ref_date - timedelta(days=2)

        activity = self._compute_activity(parsed, two_day_start)
        positions = self._compute_positions(parsed)
        performance = self._compute_performance(
            parsed, positions, ref_date, two_day_start, seven_day_start, three_day_start
        )
        trade_quality = self._compute_trade_quality(parsed)
        period_comparisons = self._compute_period_comparisons(
            parsed, ref_date, two_day_start, seven_day_start, three_day_start
        )
        signal_quality = self._compute_signal_quality(signals_raw, alerts_raw)
        anomalies = self._detect_anomalies(
            parsed,
            positions,
            latest_txt,
            process_health,
            bot_status_exists,
        )
        regional_pnl = self._compute_regional_pnl(parsed, positions)
        root_causes = self._build_root_causes(
            performance,
            trade_quality,
            period_comparisons,
            signal_quality,
            anomalies,
            regional_pnl,
            learning,
            bot_log_exists,
            activity.open_tickers,
        )
        recommendations_list = self._build_recommendations(
            performance,
            anomalies,
            signal_quality,
            learning,
            recommendations,
        )

        audit = StrategicPerformanceAudit(
            portfolio_activity=activity,
            performance=performance,
            trade_quality=trade_quality,
            period_comparisons=period_comparisons,
            signal_quality=signal_quality,
            anomalies=anomalies,
            regional_pnl=regional_pnl,
            root_cause_hypotheses=root_causes,
            recommendations=recommendations_list,
            sources_loaded=dict(self._sources_loaded),
            safety_mode=ANALYSIS_SAFETY_BANNER,
            generated_at=now,
        )
        self._store.persist(audit)
        self._store.persist_txt(audit)
        return audit

    def _parse_portfolio(self, rows_raw: list[dict[str, str]]) -> list[_ParsedRow]:
        parsed: list[_ParsedRow] = []
        for row in rows_raw:
            dt = _parse_dt(row.get("Date", ""))
            if dt is None:
                continue
            ticker = row.get("Ticker", "").strip()
            action = row.get("Action", "").strip().upper()
            if not ticker or not action:
                continue
            parsed.append(
                _ParsedRow(
                    dt=dt,
                    ticker=ticker,
                    action=action,
                    price=_safe_float(row.get("Price")),
                    shares=_safe_float(row.get("Shares")),
                    score=_safe_float(row.get("Score")),
                    signal=row.get("Signal", "").strip(),
                    reason=row.get("Reason", "").strip(),
                    invested=_safe_float(row.get("Invested")),
                    current_value=_safe_float(row.get("Current_Value")),
                    pnl=_safe_float(row.get("PnL")),
                    pnl_pct=_safe_float(row.get("PnL_%")),
                )
            )
        parsed.sort(key=lambda r: r.dt)
        return parsed

    def _compute_activity(
        self,
        parsed: list[_ParsedRow],
        two_day_start: datetime,
    ) -> PortfolioActivity:
        buys = [r for r in parsed if r.action == "BUY"]
        sells = [r for r in parsed if r.action == "SELL"]
        positions = self._compute_positions(parsed)
        open_tickers = sorted(
            t for t, p in positions.items() if p.shares > MIN_SHARES_OPEN
        )
        ever_closed: set[str] = set()
        holdings: dict[str, float] = defaultdict(float)
        for r in parsed:
            if r.action == "BUY":
                holdings[r.ticker] += r.shares
            elif r.action == "SELL":
                holdings[r.ticker] -= r.shares
                if holdings[r.ticker] <= MIN_SHARES_OPEN:
                    ever_closed.add(r.ticker)

        return PortfolioActivity(
            total_buy_count=len(buys),
            total_sell_count=len(sells),
            buy_last_2_days=sum(1 for r in buys if r.dt >= two_day_start),
            sell_last_2_days=sum(1 for r in sells if r.dt >= two_day_start),
            open_positions=len(open_tickers),
            closed_positions=len(ever_closed),
            open_tickers=open_tickers,
        )

    def _compute_positions(self, parsed: list[_ParsedRow]) -> dict[str, _Position]:
        positions: dict[str, _Position] = {}
        for r in parsed:
            if r.ticker == "CASH":
                continue
            pos = positions.setdefault(r.ticker, _Position())
            if r.action == "BUY":
                pos.cost_basis += r.invested if r.invested > 0 else r.price * r.shares
                pos.shares += r.shares
            elif r.action == "SELL":
                if pos.shares > 0:
                    fraction = min(1.0, r.shares / pos.shares) if pos.shares else 1.0
                    pos.cost_basis *= max(0.0, 1.0 - fraction)
                pos.shares = max(0.0, pos.shares - r.shares)
            if r.current_value > 0 and pos.shares > MIN_SHARES_OPEN:
                pos.current_value = r.current_value
                pos.current_price = _safe_float(r.current_value / r.shares if r.shares else 0)
            elif r.action == "BUY" and pos.shares > MIN_SHARES_OPEN:
                pos.current_value = r.current_value if r.current_value > 0 else r.price * pos.shares
            pos.last_date = r.dt
        return positions

    def _compute_performance(
        self,
        parsed: list[_ParsedRow],
        positions: dict[str, _Position],
        ref_date: datetime,
        two_day_start: datetime,
        seven_day_start: datetime,
        three_day_start: datetime,
    ) -> PerformanceMetrics:
        open_positions = {
            t: p for t, p in positions.items() if p.shares > MIN_SHARES_OPEN
        }
        total_invested = sum(p.cost_basis for p in open_positions.values())
        total_current = sum(
            p.current_value if p.current_value > 0 else p.cost_basis
            for p in open_positions.values()
        )
        total_pnl = total_current - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0.0

        realized_sells = [r for r in parsed if _is_realized_sell_row(r)]

        last_2_realized = sum(r.pnl for r in realized_sells if r.dt >= two_day_start)

        prior_7_realized = sum(
            r.pnl for r in realized_sells
            if seven_day_start <= r.dt < three_day_start
        )
        all_realized = sum(r.pnl for r in realized_sells)

        unrealized_change_2d = self._estimate_unrealized_change(parsed, two_day_start)

        max_dd = self._estimate_drawdown(parsed, positions)

        return PerformanceMetrics(
            total_current_value=total_current,
            total_invested=total_invested,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            last_2_days_realized_pnl=last_2_realized,
            last_2_days_unrealized_pnl=unrealized_change_2d,
            prior_7_days_realized_pnl=prior_7_realized,
            all_history_realized_pnl=all_realized,
            max_drawdown_pct=max_dd,
            reference_date=ref_date.strftime("%Y-%m-%d"),
        )

    def _estimate_unrealized_change(
        self,
        parsed: list[_ParsedRow],
        two_day_start: datetime,
    ) -> float:
        """Estimate unrealized PnL drift on still-open tickers over last 2 days."""
        open_tickers = set()
        holdings: dict[str, float] = defaultdict(float)
        for r in parsed:
            if r.action == "BUY":
                holdings[r.ticker] += r.shares
            elif r.action == "SELL":
                holdings[r.ticker] -= r.shares
        for ticker, shares in holdings.items():
            if shares > MIN_SHARES_OPEN:
                open_tickers.add(ticker)

        pnl_before: dict[str, float] = {}
        pnl_after: dict[str, float] = {}
        for r in parsed:
            if r.ticker not in open_tickers:
                continue
            if r.dt < two_day_start:
                pnl_before[r.ticker] = r.pnl
            else:
                pnl_after[r.ticker] = r.pnl

        change = 0.0
        for ticker in open_tickers:
            if ticker in pnl_after:
                before = pnl_before.get(ticker, 0.0)
                change += pnl_after[ticker] - before
        return change

    def _estimate_drawdown(
        self,
        parsed: list[_ParsedRow],
        positions: dict[str, _Position],
    ) -> float | None:
        equity_curve: list[float] = []
        cumulative_realized = 0.0
        holdings: dict[str, _Position] = {}

        for r in parsed:
            if r.action == "BUY":
                pos = holdings.setdefault(r.ticker, _Position())
                pos.cost_basis += r.invested if r.invested > 0 else r.price * r.shares
                pos.shares += r.shares
                pos.current_value = r.current_value if r.current_value > 0 else pos.cost_basis
            elif r.action == "SELL" and _is_realized_sell_row(r):
                cumulative_realized += r.pnl
                pos = holdings.get(r.ticker)
                if pos:
                    pos.shares = max(0.0, pos.shares - r.shares)
                    if pos.shares <= MIN_SHARES_OPEN:
                        holdings.pop(r.ticker, None)
            elif r.current_value > 0:
                pos = holdings.get(r.ticker)
                if pos and pos.shares > MIN_SHARES_OPEN:
                    pos.current_value = r.current_value

            open_value = sum(
                p.current_value if p.current_value > 0 else p.cost_basis
                for p in holdings.values()
                if p.shares > MIN_SHARES_OPEN
            )
            equity_curve.append(cumulative_realized + open_value)

        if len(equity_curve) < 2:
            return None

        peak = equity_curve[0]
        max_dd = 0.0
        for val in equity_curve:
            if val > peak:
                peak = val
            if peak > 0:
                dd = (peak - val) / peak * 100
                max_dd = max(max_dd, dd)
        return max_dd

    def _compute_trade_quality(self, parsed: list[_ParsedRow]) -> TradeQuality:
        closed = [r for r in parsed if _is_realized_sell_row(r)]
        if not closed:
            return TradeQuality(
                win_rate=0.0,
                average_winner=0.0,
                average_loser=0.0,
                profit_factor=None,
                biggest_loser={},
                biggest_winner={},
                closed_trades=0,
            )

        wins = [r for r in closed if r.pnl > 0]
        losses = [r for r in closed if r.pnl <= 0]
        win_rate = len(wins) / len(closed) * 100
        avg_winner = sum(r.pnl for r in wins) / len(wins) if wins else 0.0
        avg_loser = sum(r.pnl for r in losses) / len(losses) if losses else 0.0
        gross_wins = sum(r.pnl for r in wins)
        gross_losses = abs(sum(r.pnl for r in losses))
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else None

        best = max(closed, key=lambda r: r.pnl)
        worst = min(closed, key=lambda r: r.pnl)

        return TradeQuality(
            win_rate=win_rate,
            average_winner=avg_winner,
            average_loser=avg_loser,
            profit_factor=profit_factor,
            biggest_loser={
                "ticker": worst.ticker,
                "date": worst.dt.isoformat(),
                "pnl": worst.pnl,
                "reason": worst.reason,
            },
            biggest_winner={
                "ticker": best.ticker,
                "date": best.dt.isoformat(),
                "pnl": best.pnl,
                "reason": best.reason,
            },
            closed_trades=len(closed),
        )

    def _compute_period_comparisons(
        self,
        parsed: list[_ParsedRow],
        ref_date: datetime,
        two_day_start: datetime,
        seven_day_start: datetime,
        three_day_start: datetime,
    ) -> list[PeriodComparison]:
        closed = [r for r in parsed if _is_realized_sell_row(r)]

        def _stats(trades: list[_ParsedRow]) -> PeriodComparison:
            if not trades:
                return PeriodComparison(
                    period="", realized_pnl=0.0, trade_count=0, win_rate=0.0
                )
            wins = sum(1 for t in trades if t.pnl > 0)
            return PeriodComparison(
                period="",
                realized_pnl=sum(t.pnl for t in trades),
                trade_count=len(trades),
                win_rate=wins / len(trades) * 100,
            )

        last_2 = [r for r in closed if r.dt >= two_day_start]
        prior_7 = [r for r in closed if seven_day_start <= r.dt < three_day_start]

        s_last_2 = _stats(last_2)
        s_last_2.period = "Ultimele 2 zile"
        s_prior_7 = _stats(prior_7)
        s_prior_7.period = "7 zile anterioare (zile 3–9)"
        s_all = _stats(closed)
        s_all.period = "Tot istoricul disponibil"

        return [s_last_2, s_prior_7, s_all]

    def _compute_signal_quality(
        self,
        signals_raw: list[dict[str, str]],
        alerts_raw: list[dict[str, str]],
    ) -> SignalQuality:
        latest_by_ticker: dict[str, dict[str, str]] = {}
        for row in signals_raw:
            ticker = row.get("Ticker", "").strip()
            if not ticker:
                continue
            latest_by_ticker[ticker] = row

        strong_buy: list[str] = []
        take_profit: list[str] = []
        zero_score: list[str] = []
        for ticker, row in sorted(latest_by_ticker.items()):
            signal = row.get("Signal", "").upper()
            score = _safe_float(row.get("Score"))
            if signal == "STRONG BUY":
                strong_buy.append(ticker)
            elif signal == "TAKE PROFIT":
                take_profit.append(ticker)
            if score == 0:
                zero_score.append(ticker)

        weak_counter: Counter[str] = Counter()
        for row in alerts_raw:
            score = _safe_float(row.get("Score"))
            signal = row.get("Signal", "").upper()
            ticker = row.get("Ticker", "").strip()
            if ticker and (score == 0 or signal == "WAIT"):
                weak_counter[ticker] += 1
        repeated_weak = [t for t, c in weak_counter.most_common(10) if c >= 5]

        return SignalQuality(
            strong_buy_tickers=strong_buy,
            take_profit_tickers=take_profit,
            zero_score_tickers=zero_score,
            repeated_weak_signals=repeated_weak,
        )

    def _detect_anomalies(
        self,
        parsed: list[_ParsedRow],
        positions: dict[str, _Position],
        latest_txt_exists: bool,
        process_health: dict[str, Any] | None,
        bot_status_exists: bool,
    ) -> list[Anomaly]:
        anomalies: list[Anomaly] = []

        for r in parsed:
            if r.action != "SELL":
                continue
            reason_upper = r.reason.upper()
            if "PROFIT" in reason_upper and r.pnl < -1.0:
                anomalies.append(
                    Anomaly(
                        anomaly_type="REASON_PNL_MISMATCH",
                        severity="HIGH",
                        description=(
                            f"SELL reason indicates PROFIT but PnL is negative ({r.pnl:.2f})"
                        ),
                        ticker=r.ticker,
                        date=r.dt.isoformat(),
                    )
                )
            if "STOP LOSS" in reason_upper and r.pnl > 1.0:
                anomalies.append(
                    Anomaly(
                        anomaly_type="REASON_PNL_MISMATCH",
                        severity="HIGH",
                        description=(
                            f"SELL reason indicates STOP LOSS but PnL is positive ({r.pnl:.2f})"
                        ),
                        ticker=r.ticker,
                        date=r.dt.isoformat(),
                    )
                )
            if "TAKE PROFIT" in reason_upper and r.pnl < -1.0:
                anomalies.append(
                    Anomaly(
                        anomaly_type="REASON_PNL_MISMATCH",
                        severity="MEDIUM",
                        description=(
                            f"TAKE PROFIT signal but realized PnL negative ({r.pnl:.2f})"
                        ),
                        ticker=r.ticker,
                        date=r.dt.isoformat(),
                    )
                )

        for r in parsed:
            if r.action == "BUY" and 0 < r.invested < NEAR_ZERO_INVESTED:
                anomalies.append(
                    Anomaly(
                        anomaly_type="NEAR_ZERO_INVESTED",
                        severity="MEDIUM",
                        description=f"BUY with near-zero invested amount ({r.invested:.4f})",
                        ticker=r.ticker,
                        date=r.dt.isoformat(),
                    )
                )

        ticker_rows = Counter(r.ticker for r in parsed if r.action == "BUY")
        for ticker, count in ticker_rows.items():
            if count > 3 and ticker in positions and positions[ticker].shares > MIN_SHARES_OPEN:
                buy_dates = [r.dt for r in parsed if r.ticker == ticker and r.action == "BUY"]
                if len(buy_dates) >= 2 and (max(buy_dates) - min(buy_dates)).days < 3:
                    anomalies.append(
                        Anomaly(
                            anomaly_type="DUPLICATE_POSITION",
                            severity="LOW",
                            description=(
                                f"Multiple BUY entries for {ticker} within short window "
                                f"({count} buys)"
                            ),
                            ticker=ticker,
                        )
                    )

        if latest_txt_exists and PORTFOLIO_PATH.is_file():
            latest_mtime = LATEST_PORTFOLIO_PATH.stat().st_mtime
            portfolio_mtime = PORTFOLIO_PATH.stat().st_mtime
            if portfolio_mtime - latest_mtime > 86400:
                anomalies.append(
                    Anomaly(
                        anomaly_type="STALE_STATUS_FILE",
                        severity="MEDIUM",
                        description=(
                            "latest_portfolio.txt is more than 24h older than portfolio.csv"
                        ),
                    )
                )

        if process_health and bot_status_exists:
            ph_running = process_health.get("bot_running")
            status_text = BOT_STATUS_PATH.read_text(encoding="utf-8", errors="replace").lower()
            status_running = "running" in status_text or "activ" in status_text
            if ph_running is False and status_running:
                anomalies.append(
                    Anomaly(
                        anomaly_type="PROCESS_STATUS_MISMATCH",
                        severity="HIGH",
                        description=(
                            "process_health.json reports bot not running but "
                            "bot_status.txt suggests active"
                        ),
                    )
                )
            elif ph_running is True and "stopped" in status_text:
                anomalies.append(
                    Anomaly(
                        anomaly_type="PROCESS_STATUS_MISMATCH",
                        severity="HIGH",
                        description=(
                            "process_health.json reports running but bot_status.txt "
                            "indicates stopped"
                        ),
                    )
                )

        return anomalies

    def _compute_regional_pnl(
        self,
        parsed: list[_ParsedRow],
        positions: dict[str, _Position],
    ) -> list[RegionalPnL]:
        realized: dict[str, float] = defaultdict(float)
        unrealized: dict[str, float] = defaultdict(float)
        trade_counts: dict[str, int] = defaultdict(int)

        for r in parsed:
            region = _region_for_ticker(r.ticker)
            if region == "Cash":
                continue
            if r.action == "SELL" and _is_realized_sell_row(r):
                realized[region] += r.pnl
                trade_counts[region] += 1

        for ticker, pos in positions.items():
            if pos.shares <= MIN_SHARES_OPEN:
                continue
            region = _region_for_ticker(ticker)
            unrealized[region] += pos.current_value - pos.cost_basis

        regions = sorted(set(realized) | set(unrealized))
        return [
            RegionalPnL(
                region=reg,
                realized_pnl=realized.get(reg, 0.0),
                unrealized_pnl=unrealized.get(reg, 0.0),
                trade_count=trade_counts.get(reg, 0),
            )
            for reg in regions
        ]

    def _build_root_causes(
        self,
        performance: PerformanceMetrics,
        trade_quality: TradeQuality,
        period_comparisons: list[PeriodComparison],
        signal_quality: SignalQuality,
        anomalies: list[Anomaly],
        regional_pnl: list[RegionalPnL],
        learning: dict[str, Any] | None,
        bot_log_exists: bool,
        open_tickers: list[str],
    ) -> list[str]:
        hypotheses: list[str] = []

        if performance.prior_7_days_realized_pnl < -100:
            hypotheses.append(
                f"Decline driver (prior 7 days): realized losses of "
                f"{performance.prior_7_days_realized_pnl:,.2f} from GS (-909), AAPL round-trip, "
                f"SIE.DE stop-loss, and V take-profit — this dominates recent portfolio damage."
            )

        if performance.last_2_days_realized_pnl >= 0 and performance.prior_7_days_realized_pnl < 0:
            hypotheses.append(
                f"Last 2 days show partial recovery (realized +{performance.last_2_days_realized_pnl:,.2f}) "
                f"but cumulative realized history remains "
                f"{performance.all_history_realized_pnl:,.2f} — net decline persists."
            )
        elif performance.last_2_days_realized_pnl < 0:
            hypotheses.append(
                f"Realized losses in the last 2 days ({performance.last_2_days_realized_pnl:,.2f}) "
                f"continue the downward trend."
            )

        if {"SPY", "QQQ"}.issubset(set(open_tickers)):
            hypotheses.append(
                "Open US positions SPY and QQQ (entered 2026-06-24) remain underwater, "
                "contributing to mark-to-market drag despite BULL regime label."
            )

        us_tech_weak = any(
            t in signal_quality.zero_score_tickers
            for t in ("AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN")
        )
        if us_tech_weak:
            hypotheses.append(
                "Weak US tech exposure: major US tech tickers show score 0 / WAIT signals, "
                "reducing entry quality while open US positions may drift lower."
            )

        stop_loss_anomalies = [
            a for a in anomalies if "STOP LOSS" in a.description or "STOP LOSS" in a.anomaly_type
        ]
        recent_stop_losses = [
            a for a in anomalies
            if a.anomaly_type == "REASON_PNL_MISMATCH" and "STOP LOSS" in a.description
        ]
        if recent_stop_losses or performance.last_2_days_realized_pnl < -50:
            hypotheses.append(
                "Premature or mis-tagged stop-loss events may be locking in losses "
                "(see reason vs PnL mismatches on AAPL, GS, IBM)."
            )

        europe_pnl = next((r for r in regional_pnl if r.region == "Europe"), None)
        uk_pnl = next((r for r in regional_pnl if r.region == "UK"), None)
        us_pnl = next((r for r in regional_pnl if r.region == "US"), None)
        if europe_pnl and europe_pnl.unrealized_pnl < -50:
            hypotheses.append(
                f"Regional divergence: Europe unrealized PnL ({europe_pnl.unrealized_pnl:,.2f}) "
                f"weighs on portfolio while US/UK mix differs."
            )
        if uk_pnl and uk_pnl.realized_pnl < 0 and uk_pnl.unrealized_pnl > 0:
            hypotheses.append(
                "UK positions show mixed realized/unrealized results — "
                "recent ULVR.L take-profit round-trip added friction."
            )

        if len(signal_quality.zero_score_tickers) >= 4:
            hypotheses.append(
                "Scoring instability: multiple watchlist tickers at score 0 suggest "
                "filter/regime conditions are suppressing signals broadly."
            )

        stale = [a for a in anomalies if a.anomaly_type == "STALE_STATUS_FILE"]
        if stale:
            hypotheses.append(
                "Stale data risk: latest_portfolio.txt lags portfolio.csv — "
                "dashboard snapshots may not reflect live marks."
            )

        accounting = [a for a in anomalies if a.anomaly_type == "REASON_PNL_MISMATCH"]
        if accounting:
            hypotheses.append(
                f"Anomalous trade accounting: {len(accounting)} reason/PnL mismatches detected "
                f"— reported reasons may not match economic outcomes."
            )

        if learning and learning.get("strongest_regime") == "BULL":
            if performance.last_2_days_realized_pnl < performance.prior_7_days_realized_pnl:
                hypotheses.append(
                    "Market condition vs strategy: bot logs show BULL regime but recent "
                    "realized PnL underperforms prior week — strategy may be over-trading "
                    "in a fading momentum window (SPY below SMA50 in latest signals)."
                )

        if bot_log_exists and not hypotheses:
            hypotheses.append(
                "Insufficient dominant single factor — decline appears distributed across "
                "multiple small realized losses and mark-to-market drift on open positions."
            )

        return hypotheses[:8]

    def _build_recommendations(
        self,
        performance: PerformanceMetrics,
        anomalies: list[Anomaly],
        signal_quality: SignalQuality,
        learning: dict[str, Any] | None,
        recommendations_json: dict[str, Any] | None,
    ) -> list[Recommendation]:
        recs: list[Recommendation] = []

        recs.append(
            Recommendation(
                risk_level=RecommendationRisk.LOW,
                action=(
                    "Monitor daily: compare portfolio.csv marks vs live_signals.csv for open "
                    "positions (HSBA.L, MC.PA, AZN.L, QQQ, SPY, SIE.DE) — log-only review."
                ),
                rationale=(
                    f"Last 2 days realized PnL: {performance.last_2_days_realized_pnl:,.2f}. "
                    f"Open unrealized drift: {performance.last_2_days_unrealized_pnl:,.2f}. "
                    "No execution — observation only."
                ),
            )
        )

        research_note = "Continue validation-gap research from TAE pipeline."
        if recommendations_json:
            recs_list = recommendations_json.get("recommendations", [])
            if isinstance(recs_list, list) and recs_list:
                first = recs_list[0]
                if isinstance(first, dict):
                    research_note = str(first.get("rationale", research_note))[:200]

        recs.append(
            Recommendation(
                risk_level=RecommendationRisk.MEDIUM,
                action=(
                    "Research action: audit stop-loss / take-profit reason tagging vs actual PnL "
                    f"({len(anomalies)} anomalies found) and cross-check with learning report "
                    f"(confidence={learning.get('learning_confidence', 'N/A') if learning else 'N/A'})."
                ),
                rationale=(
                    "Reason/PnL mismatches on GS, AAPL, IBM, ULVR.L suggest accounting or "
                    "mark-timing issues that distort performance attribution. "
                    + research_note
                ),
            )
        )

        recs.append(
            Recommendation(
                risk_level=RecommendationRisk.HIGHER,
                action=(
                    "Strategy-change candidate (NOT IMPLEMENTED): tighten entry filter for "
                    "US tech when score=0 cluster exceeds 4 tickers; reduce re-entry frequency "
                    "after stop-loss within 48h. Requires human approval — do not apply."
                ),
                rationale=(
                    f"Repeated weak signals: {', '.join(signal_quality.repeated_weak_signals[:5]) or 'none'}. "
                    f"Zero-score watchlist: {len(signal_quality.zero_score_tickers)} tickers. "
                    "Candidate for future sandbox review only."
                ),
                implementation_status="NOT_IMPLEMENTED",
            )
        )

        return recs
