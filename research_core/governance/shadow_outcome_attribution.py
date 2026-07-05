"""
TAE Shadow Outcome Attribution — Phase X Sprint X.10

SHADOW_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_AUTO_POLICY_CHANGE

Counterfactual outcome evaluation for BUY_BLOCKED_BY_TAE events only.
Implements TAE_X10_EVIDENCE_MODEL.md exactly — read-only batch extension of X.9 chain.
"""

from __future__ import annotations

import csv
import json
import logging
import math
import random
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from markets.market_config import MARKETS
from markets.market_hours import get_ticker_market
from research_core.governance.shadow_validation_ledger import (
    DEFAULT_EVENTS_PATH,
    EVENT_BUY_ALLOWED,
    EVENT_BUY_BLOCKED_BY_TAE,
    MODE,
)

logger = logging.getLogger(__name__)

# live_bot.py canonical policy (read-only reference — do not import live_bot)
STOP_LOSS_PCT = -3.0
TAKE_PROFIT_PCT = 5.0
MIN_SCORE_TO_BUY = 80.0
MIN_TRADE_USD = 250.0
MAX_TRADE_USD = 2500.0
REGIME_TICKER = "SPY"

WINDOWS_TRADING_DAYS = (1, 5, 10, 20)
HEADLINE_WINDOW = 10
PROMOTION_MIN_N = 30
BOOTSTRAP_SAMPLES = 1000
MAX_CONSECUTIVE_MISSING_DAYS = 2
SIGNAL_EXPIRY_TRADING_DAYS = 10

DEFAULT_OUTCOMES_PATH = Path("tae_shadow_validation_outcomes.json")
DEFAULT_OUTCOMES_MD_PATH = Path("tae_shadow_validation_outcomes.md")
DEFAULT_PORTFOLIO_PATH = Path("portfolio.csv")
DEFAULT_SIGNALS_PATH = Path("live_signals.csv")

OUTCOMES_SCHEMA = "tae.shadow_validation_outcomes.v1"
LIVE_TRADING_IMPACT = "NONE"

SHADOW_CONTEXT_PREFIXES = (
    "[GOVERNOR_",
    "[REPLAY_",
    "[CONFIDENCE_",
    "[COUNTERFACTUAL_",
    "[KNOWLEDGE_",
    "[PROTECT_",
    "[COOLDOWN_",
    "[FADE_",
)

PRIMARY_BLOCKER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("INVALID_TAE_INDEX", re.compile(r"invalid.*report", re.I)),
    ("ELEVATED_BLOCKING_WARNINGS", re.compile(r"elevated blocking warning", re.I)),
    ("TRADING_BLOCKERS_THRESHOLD", re.compile(r"trading blocker|blocking warning count", re.I)),
    (
        "OPEN_BOOK_STRESS",
        re.compile(r"below -3% pnl|outlier-driven|open position", re.I),
    ),
    ("QUICK_HEALTH_NOT_READY", re.compile(r"quick health not ready", re.I)),
    (
        "STRATEGIC_PERFORMANCE_AUDIT",
        re.compile(r"strategic performance audit", re.I),
    ),
)


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _market_timezone(ticker: str) -> ZoneInfo:
    market = get_ticker_market(ticker)
    cfg = MARKETS.get(market) or MARKETS["US"]
    return ZoneInfo(cfg["timezone"])


def _is_trading_day(day: date, _market: str) -> bool:
    return day.weekday() < 5


def _to_market_date(dt: datetime, ticker: str) -> date:
    tz = _market_timezone(ticker)
    return dt.astimezone(tz).date()


def _add_trading_days(start: date, count: int, market: str) -> date:
    if count <= 0:
        return start
    current = start
    added = 0
    while added < count:
        current += timedelta(days=1)
        if _is_trading_day(current, market):
            added += 1
    return current


def _trading_days_between(start: date, end: date, market: str) -> int:
    if end <= start:
        return 0
    current = start
    days = 0
    while current < end:
        current += timedelta(days=1)
        if _is_trading_day(current, market):
            days += 1
    return days


def _epsilon_usd(intended_notional: float) -> float:
    return max(5.0, 0.0015 * intended_notional)


def _epsilon_pct() -> float:
    return 0.15


@dataclass
class PriceMark:
    at: datetime
    price: float
    source: str


@dataclass
class WindowSimulation:
    window_trading_days: int
    counterfactual_pnl_usd: float | None = None
    counterfactual_pnl_pct: float | None = None
    mae_pct: float | None = None
    mfe_pct: float | None = None
    exit_reason: str | None = None
    stop_hit: bool = False
    take_profit_hit: bool = False
    path_ambiguous: bool = False
    drawdown_avoided_usd: float | None = None
    missed_gain_usd: float | None = None
    spy_return_pct: float | None = None
    relative_alpha_pct: float | None = None
    intervention_value_usd: float | None = None
    classification: str = "PENDING"
    resolution_status: str = "OUTCOME_PENDING"
    data_quality: str = "FULL"
    partial_window: bool = False
    marks_used: int = 0


@dataclass
class OutcomeRecord:
    event_key: str
    timestamp: str
    ticker: str
    live_bot_cycle_id: str
    event_type: str
    entry_price: float
    entry_anchor: str
    intended_notional_usd: float
    shares: float
    advisory_action: str | None
    advisory_confidence: int | None
    block_reason: str | None
    primary_blocker: str
    contributing_blockers: list[str] = field(default_factory=list)
    shadow_context_tags: list[str] = field(default_factory=list)
    blocker_count: int = 0
    execution_attribution: str = "X8_RISK_ADVISORY"
    resolution_status: str = "OUTCOME_PENDING"
    headline_classification: str = "PENDING"
    headline_window_trading_days: int = HEADLINE_WINDOW
    signal_expired_at: str | None = None
    outcome_superseded: bool = False
    not_evaluable: bool = False
    calendar_tag: str = "WEEKEND_ONLY"
    windows: dict[str, WindowSimulation] = field(default_factory=dict)
    aggregate_weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_key": self.event_key,
            "timestamp": self.timestamp,
            "ticker": self.ticker,
            "live_bot_cycle_id": self.live_bot_cycle_id,
            "event_type": self.event_type,
            "entry_price": self.entry_price,
            "entry_anchor": self.entry_anchor,
            "intended_notional_usd": round(self.intended_notional_usd, 2),
            "shares": round(self.shares, 4),
            "advisory_action": self.advisory_action,
            "advisory_confidence": self.advisory_confidence,
            "block_reason": self.block_reason,
            "execution_attribution": self.execution_attribution,
            "primary_blocker": self.primary_blocker,
            "contributing_blockers": self.contributing_blockers,
            "shadow_context_tags": self.shadow_context_tags,
            "blocker_count": self.blocker_count,
            "resolution_status": self.resolution_status,
            "headline_classification": self.headline_classification,
            "headline_window_trading_days": self.headline_window_trading_days,
            "signal_expired_at": self.signal_expired_at,
            "outcome_superseded": self.outcome_superseded,
            "not_evaluable": self.not_evaluable,
            "calendar_tag": self.calendar_tag,
            "aggregate_weight": round(self.aggregate_weight, 4),
            "windows": {
                str(k): {
                    "window_trading_days": v.window_trading_days,
                    "counterfactual_pnl_usd": _round_or_none(v.counterfactual_pnl_usd, 2),
                    "counterfactual_pnl_pct": _round_or_none(v.counterfactual_pnl_pct, 4),
                    "mae_pct": _round_or_none(v.mae_pct, 4),
                    "mfe_pct": _round_or_none(v.mfe_pct, 4),
                    "exit_reason": v.exit_reason,
                    "stop_hit": v.stop_hit,
                    "take_profit_hit": v.take_profit_hit,
                    "path_ambiguous": v.path_ambiguous,
                    "drawdown_avoided_usd": _round_or_none(v.drawdown_avoided_usd, 2),
                    "missed_gain_usd": _round_or_none(v.missed_gain_usd, 2),
                    "spy_return_pct": _round_or_none(v.spy_return_pct, 4),
                    "relative_alpha_pct": _round_or_none(v.relative_alpha_pct, 4),
                    "intervention_value_usd": _round_or_none(v.intervention_value_usd, 2),
                    "classification": v.classification,
                    "resolution_status": v.resolution_status,
                    "data_quality": v.data_quality,
                    "partial_window": v.partial_window,
                    "marks_used": v.marks_used,
                }
                for k, v in self.windows.items()
            },
        }


def _round_or_none(value: float | None, digits: int) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def make_event_key(event: dict[str, Any]) -> str:
    return "|".join(
        [
            str(event.get("timestamp") or ""),
            str(event.get("ticker") or "").upper(),
            str(event.get("live_bot_cycle_id") or ""),
        ]
    )


def assign_primary_blocker(blockers: list[str]) -> tuple[str, list[str]]:
    blockers = [str(b).strip() for b in blockers if str(b).strip()]
    if not blockers:
        return "UNSPECIFIED_RISK_ADVISORY", []
    for code, pattern in PRIMARY_BLOCKER_PATTERNS:
        for blocker in blockers:
            if pattern.search(blocker):
                remaining = [b for b in blockers if b != blocker]
                return code, remaining
    return blockers[0], blockers[1:]


def extract_shadow_context_tags(reasons: list[str]) -> list[str]:
    tags: list[str] = []
    for reason in reasons:
        text = str(reason)
        for prefix in SHADOW_CONTEXT_PREFIXES:
            if prefix.rstrip("_") in text.upper() or prefix in text:
                tag = text.split("]", 1)[0].strip("[]") if "]" in text else prefix.strip("[")
                if tag and tag not in tags:
                    tags.append(tag)
    return tags


def compute_aggregate_weight(
    *,
    advisory_confidence: int | None,
    intended_notional_usd: float,
    data_quality: str,
    median_notional: float,
) -> float:
    conf = advisory_confidence if advisory_confidence is not None else 50
    conf_weight = min(1.25, max(0.75, 0.75 + conf / 200.0))
    if median_notional > 0:
        notional_weight = min(2.0, max(0.5, math.sqrt(intended_notional_usd / median_notional)))
    else:
        notional_weight = 1.0
    quality_weight = {"FULL": 1.0, "DEGRADED": 0.5}.get(data_quality, 0.0)
    return conf_weight * notional_weight * quality_weight


def reconstruct_notional(
    event: dict[str, Any],
    all_events: list[dict[str, Any]],
) -> tuple[float, float, str]:
    intended = event.get("intended_trade_usd")
    shares = event.get("shares")
    price = float(event.get("price") or 0)

    if isinstance(intended, (int, float)) and intended > 0:
        notional = float(intended)
        if isinstance(shares, (int, float)) and shares > 0:
            share_count = float(shares)
        elif price > 0:
            share_count = round(notional / price, 4)
        else:
            share_count = 0.0
        return notional, share_count, "EVENT_FIELD"

    cycle_id = str(event.get("live_bot_cycle_id") or "")
    cycle_allowed = [
        e
        for e in all_events
        if e.get("event_type") == EVENT_BUY_ALLOWED
        and str(e.get("live_bot_cycle_id") or "") == cycle_id
        and isinstance(e.get("intended_trade_usd"), (int, float))
        and float(e.get("intended_trade_usd")) > 0
    ]
    if cycle_allowed:
        notional = float(cycle_allowed[0]["intended_trade_usd"])
        share_count = round(notional / price, 4) if price > 0 else 0.0
        return min(notional, MAX_TRADE_USD), share_count, "SAME_CYCLE_BUY_ALLOWED"

    global_allowed = [
        float(e["intended_trade_usd"])
        for e in all_events
        if e.get("event_type") == EVENT_BUY_ALLOWED
        and isinstance(e.get("intended_trade_usd"), (int, float))
        and float(e.get("intended_trade_usd")) > 0
    ]
    if global_allowed:
        notional = sorted(global_allowed)[len(global_allowed) // 2]
        share_count = round(notional / price, 4) if price > 0 else 0.0
        return min(notional, MAX_TRADE_USD), share_count, "MEDIAN_BUY_ALLOWED"

    return 0.0, 0.0, "UNAVAILABLE"


class PriceMarkStore:
    """Read-only forward marks from portfolio.csv and live_signals.csv."""

    def __init__(
        self,
        root: Path | str = ".",
        *,
        portfolio_path: Path | str | None = None,
        signals_path: Path | str | None = None,
    ) -> None:
        self.root = Path(root)
        self.portfolio_path = Path(portfolio_path or DEFAULT_PORTFOLIO_PATH)
        self.signals_path = Path(signals_path or DEFAULT_SIGNALS_PATH)
        self._portfolio_marks: dict[str, list[PriceMark]] = {}
        self._signal_marks: dict[str, list[PriceMark]] = {}
        self._spy_marks: list[PriceMark] = []
        self._buy_dates: dict[str, list[datetime]] = {}
        self._load()

    def _load(self) -> None:
        if self.portfolio_path.is_file():
            with self.portfolio_path.open(encoding="utf-8", errors="replace", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    ticker = str(row.get("Ticker") or "").strip().upper()
                    if not ticker:
                        continue
                    dt = _parse_timestamp(row.get("Date"))
                    action = str(row.get("Action") or "").upper()
                    if action == "BUY" and dt is not None:
                        self._buy_dates.setdefault(ticker, []).append(dt)
                    price = _safe_float(row.get("Current_Price")) or _safe_float(row.get("Price"))
                    if dt is None or price is None or price <= 0:
                        continue
                    self._portfolio_marks.setdefault(ticker, []).append(
                        PriceMark(at=dt, price=price, source="portfolio.csv")
                    )
                    if ticker == REGIME_TICKER:
                        self._spy_marks.append(PriceMark(at=dt, price=price, source="portfolio.csv"))

        if self.signals_path.is_file():
            with self.signals_path.open(encoding="utf-8", errors="replace", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    ticker = str(row.get("Ticker") or "").strip().upper()
                    if not ticker:
                        continue
                    dt = _parse_timestamp(row.get("Time"))
                    price = _safe_float(row.get("Price"))
                    if dt is None or price is None or price <= 0:
                        continue
                    self._signal_marks.setdefault(ticker, []).append(
                        PriceMark(at=dt, price=price, source="live_signals.csv")
                    )
                    if ticker == REGIME_TICKER:
                        self._spy_marks.append(PriceMark(at=dt, price=price, source="live_signals.csv"))

        for marks in self._portfolio_marks.values():
            marks.sort(key=lambda m: m.at)
        for marks in self._signal_marks.values():
            marks.sort(key=lambda m: m.at)
        self._spy_marks.sort(key=lambda m: m.at)

    def has_buy_after(self, ticker: str, after: datetime) -> bool:
        return any(dt > after for dt in self._buy_dates.get(ticker.upper(), []))

    def marks_for(self, ticker: str, after: datetime) -> list[PriceMark]:
        ticker = ticker.upper()
        combined: dict[datetime, PriceMark] = {}
        for mark in self._portfolio_marks.get(ticker, []):
            if mark.at >= after:
                combined[mark.at] = mark
        for mark in self._signal_marks.get(ticker, []):
            if mark.at >= after:
                combined.setdefault(mark.at, mark)
        ordered = sorted(combined.values(), key=lambda m: m.at)
        return self._fill_small_gaps(ordered, ticker)

    def spy_marks_after(self, after: datetime) -> list[PriceMark]:
        combined: dict[datetime, PriceMark] = {}
        for mark in self._spy_marks:
            if mark.at >= after:
                combined[mark.at] = mark
        return sorted(combined.values(), key=lambda m: m.at)

    def _fill_small_gaps(self, marks: list[PriceMark], ticker: str) -> list[PriceMark]:
        if len(marks) < 2:
            return marks
        market = get_ticker_market(ticker)
        filled: list[PriceMark] = [marks[0]]
        degraded = False
        for idx in range(1, len(marks)):
            prev = filled[-1]
            cur = marks[idx]
            prev_day = _to_market_date(prev.at, ticker)
            cur_day = _to_market_date(cur.at, ticker)
            gap = _trading_days_between(prev_day, cur_day, market)
            if 1 < gap <= MAX_CONSECUTIVE_MISSING_DAYS + 1:
                mid_day = _add_trading_days(prev_day, 1, market)
                mid_dt = prev.at + (cur.at - prev.at) / 2
                interp_price = (prev.price + cur.price) / 2.0
                filled.append(PriceMark(at=mid_dt, price=interp_price, source="interpolated"))
                degraded = True
            filled.append(cur)
        if degraded:
            for mark in filled:
                if mark.source == "interpolated":
                    mark.source = "interpolated_1d_gap"
        return filled


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _simulate_path(
    *,
    entry_price: float,
    shares: float,
    notional: float,
    marks: list[PriceMark],
    window_end: date,
    ticker: str,
    spy_marks: list[PriceMark],
    entry_dt: datetime,
) -> WindowSimulation:
    market = get_ticker_market(ticker)
    sim = WindowSimulation(window_trading_days=0)
    if entry_price <= 0 or shares <= 0 or notional <= 0:
        sim.resolution_status = "NOT_EVALUABLE"
        sim.classification = "NEUTRAL"
        return sim

    if not marks:
        sim.resolution_status = "OUTCOME_PENDING"
        sim.classification = "PENDING"
        return sim

    stop_hit = False
    take_profit_hit = False
    path_ambiguous = False
    mae = 0.0
    mfe = 0.0
    exit_reason = "WINDOW_END"
    exit_price = marks[-1].price
    consecutive_missing = 0
    prev_day: date | None = None
    used = 0

    for mark in marks:
        mark_day = _to_market_date(mark.at, ticker)
        if mark_day > window_end:
            break
        if prev_day is not None:
            gap = _trading_days_between(prev_day, mark_day, market)
            if gap > MAX_CONSECUTIVE_MISSING_DAYS + 1:
                consecutive_missing = gap
                break
            if gap > 1:
                sim.data_quality = "DEGRADED"
        prev_day = mark_day
        used += 1
        pnl_pct = ((mark.price - entry_price) / entry_price) * 100.0
        mae = min(mae, pnl_pct)
        mfe = max(mfe, pnl_pct)

        if pnl_pct <= STOP_LOSS_PCT:
            stop_hit = True
            exit_reason = "STOP_LOSS"
            exit_price = mark.price
            break
        if pnl_pct >= TAKE_PROFIT_PCT:
            if stop_hit:
                path_ambiguous = True
            take_profit_hit = True
            exit_reason = "TAKE_PROFIT"
            exit_price = mark.price
            break

    if consecutive_missing > MAX_CONSECUTIVE_MISSING_DAYS:
        sim.resolution_status = "OUTCOME_PENDING"
        sim.classification = "PENDING"
        sim.marks_used = used
        return sim

    if used == 0:
        sim.resolution_status = "OUTCOME_PENDING"
        sim.classification = "PENDING"
        return sim

    pnl_usd = (exit_price - entry_price) * shares
    pnl_pct = ((exit_price - entry_price) / entry_price) * 100.0
    intervention = -pnl_usd

    spy_entry = _nearest_spy_price(spy_marks, entry_dt)
    spy_exit = _nearest_spy_price(spy_marks, marks[min(used - 1, len(marks) - 1)].at)
    spy_return = None
    relative_alpha = None
    if spy_entry and spy_exit and spy_entry > 0:
        spy_return = ((spy_exit - spy_entry) / spy_entry) * 100.0
        relative_alpha = pnl_pct - spy_return

    sim.counterfactual_pnl_usd = pnl_usd
    sim.counterfactual_pnl_pct = pnl_pct
    sim.mae_pct = mae
    sim.mfe_pct = mfe
    sim.exit_reason = exit_reason
    sim.stop_hit = stop_hit
    sim.take_profit_hit = take_profit_hit
    sim.path_ambiguous = path_ambiguous
    sim.intervention_value_usd = intervention
    sim.spy_return_pct = spy_return
    sim.relative_alpha_pct = relative_alpha
    sim.drawdown_avoided_usd = max(0.0, -pnl_usd) if pnl_usd < 0 else 0.0
    sim.missed_gain_usd = max(0.0, pnl_usd) if pnl_usd > 0 else 0.0
    sim.marks_used = used
    sim.resolution_status = "RESOLVED"
    return sim


def _nearest_spy_price(spy_marks: list[PriceMark], target: datetime) -> float | None:
    if not spy_marks:
        return None
    best = min(spy_marks, key=lambda m: abs((m.at - target).total_seconds()))
    return best.price


def classify_window(
    sim: WindowSimulation,
    *,
    notional: float,
    signal_expired: bool,
    expired_before_5d: bool,
    superseded: bool,
    unmeasurable: bool,
    not_evaluable: bool,
) -> None:
    if not_evaluable:
        sim.resolution_status = "NOT_EVALUABLE"
        sim.classification = "NEUTRAL"
        return
    if superseded:
        sim.resolution_status = "OUTCOME_SUPERSEDED"
        sim.classification = "NEUTRAL"
        return
    if unmeasurable:
        sim.resolution_status = "OUTCOME_UNMEASURABLE"
        sim.classification = "NEUTRAL"
        return
    if sim.resolution_status == "OUTCOME_PENDING":
        sim.classification = "PENDING"
        return
    if signal_expired and expired_before_5d:
        sim.resolution_status = "SIGNAL_EXPIRED"
        sim.classification = "NEUTRAL"
        return
    if sim.path_ambiguous:
        sim.classification = "NEUTRAL"
        return

    eps_usd = _epsilon_usd(notional)
    eps_pct = _epsilon_pct()
    intervention = sim.intervention_value_usd or 0.0
    pnl_pct = sim.counterfactual_pnl_pct or 0.0

    if (
        intervention > eps_usd
        or (
            (sim.mae_pct or 0.0) <= STOP_LOSS_PCT
            and sim.stop_hit
            and intervention >= 0
        )
    ):
        sim.classification = "WIN"
        return

    if (
        intervention < -eps_usd
        and not sim.stop_hit
        and pnl_pct > eps_pct
    ):
        sim.classification = "LOSS"
        return

    if abs(intervention) <= eps_usd:
        sim.classification = "NEUTRAL"
        return

    sim.classification = "NEUTRAL"


def _headline_classification(record: OutcomeRecord) -> tuple[str, str]:
    for window_days in (HEADLINE_WINDOW, 5, 1):
        key = str(window_days)
        window = record.windows.get(key)
        if window is None:
            continue
        if window.resolution_status in {
            "OUTCOME_PENDING",
            "OUTCOME_UNMEASURABLE",
            "NOT_EVALUABLE",
            "OUTCOME_SUPERSEDED",
        }:
            if window.classification == "PENDING":
                continue
        return window.classification, window.resolution_status
    return "PENDING", "OUTCOME_PENDING"


def evaluate_blocked_event(
    event: dict[str, Any],
    all_events: list[dict[str, Any]],
    marks: PriceMarkStore,
    *,
    median_notional: float,
    as_of: datetime | None = None,
) -> OutcomeRecord:
    as_of = as_of or datetime.now(timezone.utc)
    ticker = str(event.get("ticker") or "").upper()
    event_dt = _parse_timestamp(event.get("timestamp"))
    if event_dt is None:
        event_dt = as_of
    price = float(event.get("price") or 0)
    market = get_ticker_market(ticker)

    blockers = list(event.get("advisory_blockers") or [])
    reasons = list(event.get("advisory_reasons") or [])
    primary, contributing = assign_primary_blocker(blockers)
    tags = extract_shadow_context_tags(reasons)

    notional, shares, sizing_source = reconstruct_notional(event, all_events)
    not_evaluable = notional < MIN_TRADE_USD or price <= 0 or shares <= 0

    entry_anchor = "EVENT_PRICE"
    record = OutcomeRecord(
        event_key=make_event_key(event),
        timestamp=str(event.get("timestamp") or ""),
        ticker=ticker,
        live_bot_cycle_id=str(event.get("live_bot_cycle_id") or ""),
        event_type=str(event.get("event_type") or ""),
        entry_price=price,
        entry_anchor=entry_anchor,
        intended_notional_usd=notional,
        shares=shares if shares > 0 else round(notional / price, 4) if price > 0 else 0.0,
        advisory_action=event.get("advisory_action"),
        advisory_confidence=event.get("advisory_confidence"),
        block_reason=event.get("block_reason"),
        primary_blocker=primary,
        contributing_blockers=contributing,
        shadow_context_tags=tags,
        blocker_count=len(blockers),
        not_evaluable=not_evaluable,
    )

    if not_evaluable:
        record.resolution_status = "NOT_EVALUABLE"
        record.headline_classification = "NEUTRAL"
        for days in WINDOWS_TRADING_DAYS:
            sim = WindowSimulation(window_trading_days=days)
            classify_window(
                sim,
                notional=notional,
                signal_expired=False,
                expired_before_5d=False,
                superseded=False,
                unmeasurable=False,
                not_evaluable=True,
            )
            record.windows[str(days)] = sim
        return record

    superseded = marks.has_buy_after(ticker, event_dt)
    event_day = _to_market_date(event_dt, ticker)
    expiry_day = _add_trading_days(event_day, SIGNAL_EXPIRY_TRADING_DAYS, market)
    signal_expired = as_of.date() >= expiry_day or superseded
    expired_before_5d = _add_trading_days(event_day, 5, market) > min(
        _to_market_date(as_of, ticker),
        expiry_day if signal_expired else _add_trading_days(event_day, 999, market),
    ) and signal_expired

    forward_marks = marks.marks_for(ticker, event_dt)
    spy_marks = marks.spy_marks_after(event_dt)

    if not forward_marks and _to_market_date(as_of, ticker) <= event_day:
        record.resolution_status = "OUTCOME_PENDING"
        record.headline_classification = "PENDING"
        for days in WINDOWS_TRADING_DAYS:
            sim = WindowSimulation(window_trading_days=days, classification="PENDING")
            record.windows[str(days)] = sim
        return record

    data_quality = "FULL"
    for days in WINDOWS_TRADING_DAYS:
        window_end = _add_trading_days(event_day, days, market)
        effective_end = min(window_end, expiry_day) if signal_expired else window_end
        partial = signal_expired and effective_end < window_end
        window_marks = [
            m
            for m in forward_marks
            if _to_market_date(m.at, ticker) <= effective_end
        ]
        sim = _simulate_path(
            entry_price=price,
            shares=record.shares,
            notional=notional,
            marks=window_marks,
            window_end=effective_end,
            ticker=ticker,
            spy_marks=spy_marks,
            entry_dt=event_dt,
        )
        sim.window_trading_days = days
        sim.partial_window = partial
        if sim.data_quality == "DEGRADED":
            data_quality = "DEGRADED"
        unmeasurable = sim.resolution_status == "OUTCOME_PENDING" and not window_marks
        classify_window(
            sim,
            notional=notional,
            signal_expired=signal_expired,
            expired_before_5d=expired_before_5d and days >= 5,
            superseded=superseded,
            unmeasurable=unmeasurable,
            not_evaluable=False,
        )
        record.windows[str(days)] = sim

    record.aggregate_weight = compute_aggregate_weight(
        advisory_confidence=record.advisory_confidence,
        intended_notional_usd=notional,
        data_quality=data_quality,
        median_notional=median_notional,
    )
    if superseded:
        record.outcome_superseded = True
        record.resolution_status = "OUTCOME_SUPERSEDED"
    elif signal_expired:
        record.signal_expired_at = expiry_day.isoformat()
        record.resolution_status = "SIGNAL_EXPIRED"
    else:
        headline = record.windows.get(str(HEADLINE_WINDOW))
        if headline and headline.resolution_status == "RESOLVED":
            record.resolution_status = "RESOLVED"
        elif any(w.classification == "PENDING" for w in record.windows.values()):
            record.resolution_status = "OUTCOME_PENDING"
        else:
            record.resolution_status = "RESOLVED"

    record.headline_classification, _ = _headline_classification(record)
    return record


def bootstrap_ci(values: list[float], *, samples: int = BOOTSTRAP_SAMPLES) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    if len(values) == 1:
        v = values[0]
        return v, v, v
    rng = random.Random(42)
    means: list[float] = []
    for _ in range(samples):
        draw = [values[rng.randrange(len(values))] for _ in range(len(values))]
        means.append(sum(draw) / len(draw))
    means.sort()
    lower = means[int(0.025 * len(means))]
    upper = means[int(0.975 * len(means)) - 1]
    return sum(values) / len(values), lower, upper


def build_aggregate_statistics(records: list[OutcomeRecord]) -> dict[str, Any]:
    eligible = [r for r in records if not r.not_evaluable and not r.outcome_superseded]
    resolved = [
        r
        for r in eligible
        if r.resolution_status in {"RESOLVED", "SIGNAL_EXPIRED"}
        and r.windows.get(str(HEADLINE_WINDOW), WindowSimulation(0)).resolution_status
        in {"RESOLVED", "SIGNAL_EXPIRED"}
    ]

    def window_stats(window_key: str) -> dict[str, Any]:
        wins = losses = neutrals = pending = 0
        interventions: list[float] = []
        weights: list[float] = []
        for record in eligible:
            window = record.windows.get(window_key)
            if window is None:
                continue
            if window.classification == "WIN":
                wins += 1
            elif window.classification == "LOSS":
                losses += 1
            elif window.classification == "PENDING":
                pending += 1
            else:
                neutrals += 1
            if window.intervention_value_usd is not None and window.classification in {
                "WIN",
                "LOSS",
                "NEUTRAL",
            }:
                if window.data_quality != "FULL" and window.classification == "NEUTRAL":
                    pass
                else:
                    interventions.append(window.intervention_value_usd)
                    weights.append(record.aggregate_weight if window.data_quality == "FULL" else record.aggregate_weight * 0.5)
        mean_iv = sum(interventions) / len(interventions) if interventions else 0.0
        mean_w = (
            sum(i * w for i, w in zip(interventions, weights)) / sum(weights)
            if weights
            else mean_iv
        )
        _, ci_low, ci_high = bootstrap_ci(interventions)
        return {
            "window_trading_days": int(window_key),
            "eligible_events": len(eligible),
            "resolved_events": len(resolved),
            "win": wins,
            "loss": losses,
            "neutral": neutrals,
            "pending": pending,
            "mean_intervention_value_usd": round(mean_iv, 2),
            "weighted_mean_intervention_value_usd": round(mean_w, 2),
            "bootstrap_95ci_low": round(ci_low, 2),
            "bootstrap_95ci_high": round(ci_high, 2),
        }

    by_blocker: dict[str, Any] = {}
    blockers = sorted({r.primary_blocker for r in eligible})
    for blocker in blockers:
        subset = [r for r in eligible if r.primary_blocker == blocker]
        interventions = [
            r.windows[str(HEADLINE_WINDOW)].intervention_value_usd
            for r in subset
            if str(HEADLINE_WINDOW) in r.windows
            and r.windows[str(HEADLINE_WINDOW)].intervention_value_usd is not None
            and r.windows[str(HEADLINE_WINDOW)].classification in {"WIN", "LOSS", "NEUTRAL"}
        ]
        mean, ci_low, ci_high = bootstrap_ci([float(x) for x in interventions])
        wins = sum(
            1
            for r in subset
            if r.windows.get(str(HEADLINE_WINDOW)) and r.windows[str(HEADLINE_WINDOW)].classification == "WIN"
        )
        losses = sum(
            1
            for r in subset
            if r.windows.get(str(HEADLINE_WINDOW)) and r.windows[str(HEADLINE_WINDOW)].classification == "LOSS"
        )
        by_blocker[blocker] = {
            "count": len(subset),
            "win": wins,
            "loss": losses,
            "mean_intervention_value_usd": round(mean, 2),
            "bootstrap_95ci_low": round(ci_low, 2),
            "bootstrap_95ci_high": round(ci_high, 2),
            "promotion_eligible": len(subset) >= PROMOTION_MIN_N and not (ci_low <= 0 <= ci_high),
        }

    return {
        "headline_window_trading_days": HEADLINE_WINDOW,
        "eligible_events": len(eligible),
        "resolved_events": len(resolved),
        "windows": {str(d): window_stats(str(d)) for d in WINDOWS_TRADING_DAYS},
        "by_primary_blocker": by_blocker,
    }


def build_learning_promotion(aggregate: dict[str, Any]) -> dict[str, Any]:
    headline = aggregate.get("windows", {}).get(str(HEADLINE_WINDOW), {})
    n = int(headline.get("eligible_events") or 0)
    ci_low = float(headline.get("bootstrap_95ci_low") or 0.0)
    ci_high = float(headline.get("bootstrap_95ci_high") or 0.0)
    significant = n >= PROMOTION_MIN_N and not (ci_low <= 0 <= ci_high)
    return {
        "promotion_min_n": PROMOTION_MIN_N,
        "eligible_count": n,
        "confidence_significant": significant,
        "policy_change_allowed": False,
        "recommendation": (
            "AGGREGATE_EVIDENCE_READY_FOR_ARCHITECT_REVIEW"
            if significant
            else "INSUFFICIENT_SAMPLE_OR_INCONCLUSIVE"
        ),
        "evidence_for_knowledge_base": [] if not significant else [
            {
                "source": "X10_SHADOW_OUTCOME_ATTRIBUTION",
                "pattern_type": "LIVE_BUY_BLOCK_EFFECTIVENESS",
                "confidence": "MEDIUM" if n < 50 else "HIGH",
                "detail": (
                    f"Headline 10D mean intervention USD "
                    f"{headline.get('mean_intervention_value_usd')} "
                    f"CI [{ci_low}, {ci_high}] n={n}"
                ),
                "shadow_recommendation": "DO_NOT_PROMOTE_TO_LIVE",
            }
        ],
    }


def derive_outcome_tracking_status(records: list[OutcomeRecord]) -> str:
    resolved_10d = [
        r
        for r in records
        if not r.not_evaluable
        and not r.outcome_superseded
        and r.windows.get(str(HEADLINE_WINDOW))
        and r.windows[str(HEADLINE_WINDOW)].resolution_status in {"RESOLVED", "SIGNAL_EXPIRED"}
    ]
    if not records:
        return "PENDING_NEXT_PHASE"
    if not any(r.event_type == EVENT_BUY_BLOCKED_BY_TAE for r in records):
        return "PENDING_NEXT_PHASE"
    if resolved_10d:
        return "ACTIVE"
    return "OUTCOME_PENDING"


def build_outcomes_report(
    events: list[dict[str, Any]],
    *,
    root: Path | str = ".",
    events_path: Path | str | None = None,
    portfolio_path: Path | str | None = None,
    signals_path: Path | str | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    as_of = as_of or datetime.now(timezone.utc)
    blocked = [e for e in events if e.get("event_type") == EVENT_BUY_BLOCKED_BY_TAE]
    allowed_notionals = [
        float(e["intended_trade_usd"])
        for e in events
        if e.get("event_type") == EVENT_BUY_ALLOWED
        and isinstance(e.get("intended_trade_usd"), (int, float))
        and float(e.get("intended_trade_usd")) > 0
    ]
    median_notional = (
        sorted(allowed_notionals)[len(allowed_notionals) // 2] if allowed_notionals else 1000.0
    )

    marks = PriceMarkStore(
        root,
        portfolio_path=portfolio_path,
        signals_path=signals_path,
    )
    records = [
        evaluate_blocked_event(
            event,
            events,
            marks,
            median_notional=median_notional,
            as_of=as_of,
        )
        for event in blocked
    ]
    aggregate = build_aggregate_statistics(records)
    learning = build_learning_promotion(aggregate)
    status = derive_outcome_tracking_status(records)

    return {
        "schema": OUTCOMES_SCHEMA,
        "generated_at": as_of.isoformat(),
        "mode": MODE,
        "live_trading_impact": LIVE_TRADING_IMPACT,
        "methodology": "TAE_X10_EVIDENCE_MODEL.md",
        "scope_event_type": EVENT_BUY_BLOCKED_BY_TAE,
        "source_events_path": str(events_path or DEFAULT_EVENTS_PATH),
        "outcome_tracking_status": status,
        "eligible_events": len(blocked),
        "resolved_events": [r.to_dict() for r in records],
        "aggregate_statistics": aggregate,
        "learning_promotion": learning,
        "policy_change_allowed": False,
    }


def render_outcomes_md(report: dict[str, Any]) -> str:
    lines = [
        "# TAE Shadow Validation Outcomes (X.10)",
        "",
        f"**Generated:** {report.get('generated_at')}",
        f"**Status:** {report.get('outcome_tracking_status')}",
        f"**Eligible blocked events:** {report.get('eligible_events')}",
        "",
        "## Headline aggregate (10 trading days)",
        "",
    ]
    headline = report.get("aggregate_statistics", {}).get("windows", {}).get("10", {})
    lines.extend(
        [
            f"- WIN: {headline.get('win', 0)}",
            f"- LOSS: {headline.get('loss', 0)}",
            f"- NEUTRAL: {headline.get('neutral', 0)}",
            f"- PENDING: {headline.get('pending', 0)}",
            f"- Mean intervention USD: {headline.get('mean_intervention_value_usd')}",
            "",
            "## Learning promotion",
            "",
            f"- Recommendation: {report.get('learning_promotion', {}).get('recommendation')}",
            f"- Policy change allowed: {report.get('policy_change_allowed')}",
            "",
        ]
    )
    return "\n".join(lines)


def persist_outcomes_report(
    report: dict[str, Any],
    *,
    json_path: Path | str | None = None,
    md_path: Path | str | None = None,
) -> tuple[Path, Path]:
    json_out = Path(json_path or DEFAULT_OUTCOMES_PATH)
    md_out = Path(md_path or DEFAULT_OUTCOMES_MD_PATH)
    json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_out.write_text(render_outcomes_md(report), encoding="utf-8")
    return json_out, md_out


def run_outcome_attribution(
    *,
    root: Path | str = ".",
    events_path: Path | str | None = None,
    portfolio_path: Path | str | None = None,
    signals_path: Path | str | None = None,
    json_path: Path | str | None = None,
    md_path: Path | str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    from tae_shadow_validation_report import load_events

    root_path = Path(root)
    events = load_events(events_path or root_path / DEFAULT_EVENTS_PATH)
    report = build_outcomes_report(
        events,
        root=root_path,
        events_path=events_path,
        portfolio_path=portfolio_path,
        signals_path=signals_path,
    )
    if not dry_run:
        persist_outcomes_report(report, json_path=json_path, md_path=md_path)
    return report
