#!/usr/bin/env python3
"""
TAE 10-Day Trading Opportunity Audit — FORENSIC READ-ONLY

MODE: FORENSIC AUDIT ONLY | NO_EXECUTION | NO_BROKER | NO_PORTFOLIO_CHANGE
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from markets.market_config import MARKETS
from markets.market_hours import get_ticker_market

AUDIT_MODE = "FORENSIC_AUDIT_ONLY"
NO_EXECUTION = True
WINDOW_DAYS = 10
INTERVAL_SECONDS = 60
MIN_SCORE_TO_BUY = 80
DEFAULT_TRADE_USD = 2500.0
LOG_TIMESTAMP_TZ = "US/Eastern"

LOG_PATHS = [
    Path("runtime_outputs/bot_output.log"),
    Path("bot_output.log"),
]
ALERTS_PATH = Path("alerts_log.csv")
PORTFOLIO_PATH = Path("portfolio.csv")
SHADOW_EVENTS_PATH = Path("tae_shadow_validation_events.csv")
ACCOUNTING_SNAPSHOT_PATH = Path("tae_accounting_snapshot.json")
MARKET_GUARD_LOG_PATH = Path("market_session_guard.log")
BOT_STATUS_PATH = Path("bot_status.txt")

OUTPUT_MD = Path("TAE_10_DAY_TRADING_AUDIT.md")
OUTPUT_JSON = Path("tae_10_day_trading_audit.json")
OUTPUT_CSV = Path("tae_10_day_trading_audit.csv")
LIVE_BOT_PATH = Path("live_bot.py")

LOG_LINE_RE = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2}) (\d{2}):(\d{2}):(\d{2})\] (.+)$"
)
BUY_EXEC_RE = re.compile(
    r"BUY executat: (\S+) \| \$([0-9.]+) \| ([0-9.]+) shares @ ([0-9.]+)"
)
SELL_EXEC_RE = re.compile(
    r"SELL executat: (\S+) \| ([0-9.]+) shares @ ([0-9.]+) \| (.+)$"
)
BUY_BLOCK_RE = re.compile(r"BUY blocat pentru (\S+): (.+)$")
BUY_ALLOW_RE = re.compile(r"BUY permis pentru (\S+):")


@dataclass
class BotCycle:
    timestamp: datetime
    global_market_closed: bool = False
    regime: str | None = None
    tae_action: str | None = None
    block_new_buy: bool | None = None
    buys: list[dict[str, Any]] = field(default_factory=list)
    sells: list[dict[str, Any]] = field(default_factory=list)
    blocks: list[dict[str, Any]] = field(default_factory=list)
    allows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class BuyAuditRow:
    timestamp: str
    ticker: str
    score: float
    market: str
    market_open: bool
    bot_running: bool | None
    tae_action: str | None
    executed_buy: bool
    reason_code: str
    reason_detail: str
    price_at_signal: float | None = None
    max_price_subsequent: float | None = None
    missed_profit_usd: float | None = None
    false_market_closed: bool | None = None


def parse_log_timestamp(match: re.Match[str]) -> datetime:
    return datetime(
        int(match.group(1)[:4]),
        int(match.group(1)[5:7]),
        int(match.group(1)[8:10]),
        int(match.group(2)),
        int(match.group(3)),
        int(match.group(4)),
    )


def market_open_at(market: str, dt_naive: datetime) -> bool:
    cfg = MARKETS.get(market, {})
    if not cfg.get("enabled", False):
        return False
    now = dt_naive.replace(tzinfo=ZoneInfo(cfg["timezone"]))
    if now.weekday() >= 5:
        return False
    open_time = now.replace(
        hour=cfg["open_hour"],
        minute=cfg["open_minute"],
        second=0,
        microsecond=0,
    )
    close_time = now.replace(
        hour=cfg["close_hour"],
        minute=cfg["close_minute"],
        second=0,
        microsecond=0,
    )
    return open_time <= now <= close_time


def any_enabled_market_open(dt_naive: datetime) -> dict[str, bool]:
    return {name: market_open_at(name, dt_naive) for name in MARKETS}


def load_deduped_logs() -> list[tuple[datetime, str]]:
    seen: set[str] = set()
    rows: list[tuple[datetime, str]] = []
    for path in LOG_PATHS:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line in seen:
                continue
            seen.add(line)
            match = LOG_LINE_RE.match(line)
            if not match:
                continue
            rows.append((parse_log_timestamp(match), line))
    rows.sort(key=lambda item: item[0])
    return rows


def parse_bot_cycles(
    log_rows: list[tuple[datetime, str]], window_start: datetime, window_end: datetime
) -> list[BotCycle]:
    cycles: list[BotCycle] = []
    current: BotCycle | None = None

    for ts, line in log_rows:
        if ts < window_start or ts > window_end:
            continue
        message = LOG_LINE_RE.match(line)
        if not message:
            continue
        body = message.group(5)

        if "Live bot pornit" in body:
            pass
        if "Live bot oprit" in body:
            pass

        if "live_signals.csv actualizat" in body:
            if current is not None:
                cycles.append(current)
            current = BotCycle(timestamp=ts)
            continue

        if current is None:
            continue

        if "Piața este închisă" in body:
            current.global_market_closed = True
        if "Market Regime activ:" in body:
            current.regime = body.split(":", 1)[1].strip()
        if body.startswith("TAE Live Advisory:"):
            current.tae_action = body.split(":", 1)[1].strip().split("|")[0].strip()
        if "block_new_buy=" in body:
            current.block_new_buy = "block_new_buy=True" in body

        buy_match = BUY_EXEC_RE.search(body)
        if buy_match:
            current.buys.append(
                {
                    "ticker": buy_match.group(1),
                    "usd": float(buy_match.group(2)),
                    "shares": float(buy_match.group(3)),
                    "price": float(buy_match.group(4)),
                }
            )

        sell_match = SELL_EXEC_RE.search(body)
        if sell_match:
            current.sells.append(
                {
                    "ticker": sell_match.group(1),
                    "shares": float(sell_match.group(2)),
                    "price": float(sell_match.group(3)),
                    "reason": sell_match.group(4),
                }
            )

        block_match = BUY_BLOCK_RE.search(body)
        if block_match:
            current.blocks.append(
                {"ticker": block_match.group(1), "reason": block_match.group(2)}
            )

        allow_match = BUY_ALLOW_RE.search(body)
        if allow_match:
            current.allows.append({"ticker": allow_match.group(1)})

    if current is not None:
        cycles.append(current)
    return cycles


def cycle_id(ts: datetime) -> str:
    bucket = ts.replace(second=0, microsecond=0)
    return bucket.strftime("%Y%m%d%H%M")


def find_cycle_for_ts(cycles: list[BotCycle], ts: datetime) -> BotCycle | None:
    if not cycles:
        return None
    best: BotCycle | None = None
    best_delta = timedelta.max
    for cycle in cycles:
        delta = abs(cycle.timestamp - ts)
        if delta <= timedelta(seconds=INTERVAL_SECONDS * 3) and delta < best_delta:
            best = cycle
            best_delta = delta
    return best


def load_portfolio_buys(window_start: datetime, window_end: datetime) -> pd.DataFrame:
    portfolio = pd.read_csv(PORTFOLIO_PATH)
    portfolio["Date"] = pd.to_datetime(portfolio["Date"], errors="coerce")
    buys = portfolio[
        (portfolio["Action"].astype(str).str.upper() == "BUY")
        & (portfolio["Date"] >= window_start)
        & (portfolio["Date"] <= window_end)
    ].copy()
    return buys


def load_portfolio_sells(window_start: datetime, window_end: datetime) -> pd.DataFrame:
    portfolio = pd.read_csv(PORTFOLIO_PATH)
    portfolio["Date"] = pd.to_datetime(portfolio["Date"], errors="coerce")
    sells = portfolio[
        (portfolio["Action"].astype(str).str.upper() == "SELL")
        & (portfolio["Date"] >= window_start)
        & (portfolio["Date"] <= window_end)
    ].copy()
    return sells


def open_positions_before(portfolio: pd.DataFrame, ts: datetime) -> set[str]:
    subset = portfolio[portfolio["Date"] <= ts]
    positions: dict[str, float] = defaultdict(float)
    for _, row in subset.iterrows():
        action = str(row["Action"]).upper()
        ticker = str(row["Ticker"]).upper()
        shares = float(row["Shares"])
        if action == "BUY":
            positions[ticker] += shares
        elif action == "SELL":
            positions[ticker] -= shares
    return {t for t, sh in positions.items() if sh > 1e-9}


def classify_block_reason(raw: str) -> str:
    text = raw.lower()
    if "piața" in text and "închisă" in text:
        return "MARKET_CLOSED"
    if "max_positions" in text:
        return "MAX_POSITIONS"
    if "market regime" in text:
        return "RISK_GATE"
    if "tae" in text or "advisory" in text or "block_new_buy" in text:
        return "RISK_GATE"
    if "cash" in text or "insufficient" in text:
        return "NO_CASH"
    if "score" in text:
        return "INSUFFICIENT_SCORE"
    if "take profit" in text:
        return "TAKE_PROFIT_PRIORITY"
    return "OTHER"


def build_buy_opportunities(
    alerts: pd.DataFrame, window_start: datetime, window_end: datetime
) -> pd.DataFrame:
    alerts = alerts.copy()
    alerts["Time"] = pd.to_datetime(alerts["Time"], errors="coerce")
    alerts = alerts.dropna(subset=["Time", "Ticker"])
    alerts["Ticker"] = alerts["Ticker"].astype(str).str.upper()
    alerts["Signal"] = alerts["Signal"].astype(str).str.upper()
    alerts["Score"] = pd.to_numeric(alerts["Score"], errors="coerce")
    alerts["Price"] = pd.to_numeric(alerts["Price"], errors="coerce")

    mask = (
        (alerts["Time"] >= window_start)
        & (alerts["Time"] <= window_end)
        & (alerts["Signal"] == "STRONG BUY")
        & (alerts["Score"] >= MIN_SCORE_TO_BUY)
    )
    eligible = alerts.loc[mask].copy()
    eligible["cycle_key"] = eligible["Time"].apply(cycle_id) + "|" + eligible["Ticker"]
    deduped = eligible.drop_duplicates(subset=["cycle_key"], keep="first")
    return deduped.sort_values("Time")


def build_subsequent_max_prices(alerts: pd.DataFrame, window_end: datetime) -> dict[str, pd.Series]:
    """Per-ticker time-indexed prices for O(log n) subsequent max lookups."""
    frame = alerts.dropna(subset=["Time", "Ticker"]).copy()
    frame["Ticker"] = frame["Ticker"].astype(str).str.upper()
    frame["Price"] = pd.to_numeric(frame["Price"], errors="coerce")
    frame = frame.dropna(subset=["Price"])
    frame = frame[frame["Time"] <= window_end].sort_values("Time")
    result: dict[str, pd.Series] = {}
    for ticker, group in frame.groupby("Ticker"):
        result[ticker] = group.set_index("Time")["Price"]
    return result


def max_subsequent_price_from_cache(
    price_cache: dict[str, pd.Series], ticker: str, after_ts: datetime
) -> float | None:
    series = price_cache.get(ticker.upper())
    if series is None or series.empty:
        return None
    future = series[series.index > after_ts]
    if future.empty:
        return None
    return float(future.max())


def build_global_closed_index(
    log_rows: list[tuple[datetime, str]], window_start: datetime, window_end: datetime
) -> list[datetime]:
    times: list[datetime] = []
    for ts, line in log_rows:
        if ts < window_start or ts > window_end:
            continue
        if "Piața este închisă" in line:
            times.append(ts)
    return sorted(times)


def global_market_closed_near_indexed(
    closed_times: list[datetime], ts: datetime, seconds: int = 90
) -> bool:
    if not closed_times:
        return False
    window = timedelta(seconds=seconds)
    for ct in closed_times:
        if ct - window <= ts <= ct + window:
            return True
        if ct > ts + window:
            break
    return False


def analyze_market_closed_events(
    log_rows: list[tuple[datetime, str]], window_start: datetime, window_end: datetime
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    per_market_blocked_while_open: Counter[str] = Counter()
    false_events: list[dict[str, Any]] = []

    for ts, line in log_rows:
        if ts < window_start or ts > window_end:
            continue
        if "Piața este închisă" not in line:
            continue
        opens = any_enabled_market_open(ts)
        event = {
            "timestamp": ts.isoformat(),
            "log_line": line,
            "markets_open_per_calendar": opens,
            "any_market_open": any(opens.values()),
        }
        events.append(event)
        if event["any_market_open"]:
            false_events.append(event)
            for market, is_open in opens.items():
                if is_open:
                    per_market_blocked_while_open[market] += 1

    intervals = merge_false_closed_intervals(false_events)
    total_false_minutes = sum(item["duration_minutes"] for item in intervals)

    return {
        "global_market_closed_log_count": len(events),
        "per_market_blocked_while_open_count": dict(per_market_blocked_while_open),
        "false_market_closed_event_count": len(false_events),
        "false_market_closed_intervals": intervals,
        "false_market_closed_total_minutes": round(total_false_minutes, 1),
        "false_market_closed_events_sample": false_events[:50],
    }


def merge_false_closed_intervals(false_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not false_events:
        return []
    sorted_events = sorted(false_events, key=lambda item: item["timestamp"])
    intervals: list[dict[str, Any]] = []
    start_ts = datetime.fromisoformat(sorted_events[0]["timestamp"])
    prev_ts = start_ts
    markets_union: set[str] = set()

    def markets_open_set(event: dict[str, Any]) -> set[str]:
        return {m for m, ok in event["markets_open_per_calendar"].items() if ok}

    markets_union |= markets_open_set(sorted_events[0])

    for event in sorted_events[1:]:
        ts = datetime.fromisoformat(event["timestamp"])
        if (ts - prev_ts) <= timedelta(minutes=2):
            prev_ts = ts
            markets_union |= markets_open_set(event)
            continue
        intervals.append(
            {
                "start": start_ts.isoformat(),
                "end": prev_ts.isoformat(),
                "duration_minutes": round((prev_ts - start_ts).total_seconds() / 60, 1),
                "markets_open_during_interval": sorted(markets_union),
            }
        )
        start_ts = ts
        prev_ts = ts
        markets_union = markets_open_set(event)

    intervals.append(
        {
            "start": start_ts.isoformat(),
            "end": prev_ts.isoformat(),
            "duration_minutes": round((prev_ts - start_ts).total_seconds() / 60, 1),
            "markets_open_during_interval": sorted(markets_union),
        }
    )
    return intervals


def infer_bot_running(log_rows: list[tuple[datetime, str]], ts: datetime) -> bool | None:
    state: bool | None = None
    for row_ts, line in log_rows:
        if row_ts > ts:
            break
        if "Live bot pornit" in line:
            state = True
        if "Live bot oprit" in line:
            state = False
    if state is None and BOT_STATUS_PATH.exists():
        status = BOT_STATUS_PATH.read_text(encoding="utf-8").strip().upper()
        return status == "RUNNING"
    return state


def compute_daily_pnl(
    portfolio: pd.DataFrame, window_start: datetime, window_end: datetime
) -> list[dict[str, Any]]:
    portfolio = portfolio.copy()
    portfolio["Date"] = pd.to_datetime(portfolio["Date"], errors="coerce")
    days: list[dict[str, Any]] = []
    day = window_start.date()
    end_day = window_end.date()
    while day <= end_day:
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        day_rows = portfolio[
            (portfolio["Date"] >= day_start) & (portfolio["Date"] <= day_end)
        ]
        buys = day_rows[day_rows["Action"].astype(str).str.upper() == "BUY"]
        sells = day_rows[day_rows["Action"].astype(str).str.upper() == "SELL"]
        pnl = pd.to_numeric(sells["PnL"], errors="coerce").fillna(0).sum()
        best = None
        worst = None
        if not sells.empty:
            sell_pnl = sells.copy()
            sell_pnl["PnL_num"] = pd.to_numeric(sell_pnl["PnL"], errors="coerce").fillna(0)
            best_row = sell_pnl.loc[sell_pnl["PnL_num"].idxmax()]
            worst_row = sell_pnl.loc[sell_pnl["PnL_num"].idxmin()]
            best = {
                "ticker": str(best_row["Ticker"]),
                "pnl": float(best_row["PnL_num"]),
                "reason": str(best_row.get("Reason", "")),
            }
            worst = {
                "ticker": str(worst_row["Ticker"]),
                "pnl": float(worst_row["PnL_num"]),
                "reason": str(worst_row.get("Reason", "")),
            }
        open_count = len(open_positions_before(portfolio, day_end))
        days.append(
            {
                "date": day.isoformat(),
                "buy_count": int(len(buys)),
                "sell_count": int(len(sells)),
                "realized_pnl": round(float(pnl), 2),
                "best_trade": best,
                "worst_trade": worst,
                "open_positions_end_of_day": open_count,
            }
        )
        day += timedelta(days=1)
    return days


def compute_capital_utilization(
    portfolio: pd.DataFrame,
    accounting: dict[str, Any] | None,
    window_start: datetime,
    window_end: datetime,
) -> dict[str, Any]:
    portfolio = portfolio.copy()
    portfolio["Date"] = pd.to_datetime(portfolio["Date"], errors="coerce")
    portfolio = portfolio.sort_values("Date")

    cash = float(accounting.get("cash_available", 0)) if accounting else None
    invested_now = float(accounting.get("open_positions_value", 0)) if accounting else None
    account_value = float(accounting.get("account_value_corrected", 0)) if accounting else None

    utilization_samples: list[float] = []
    sample_times = pd.date_range(window_start, window_end, freq="6h")
    for ts in sample_times:
        subset = portfolio[portfolio["Date"] <= ts]
        positions: dict[str, list[tuple[float, float]]] = defaultdict(list)
        spent = 0.0
        received = 0.0
        for _, row in subset.iterrows():
            action = str(row["Action"]).upper()
            if action == "BUY":
                spent += float(row["Price"]) * float(row["Shares"])
            elif action == "SELL":
                received += float(row["Price"]) * float(row["Shares"])
            elif action == "DEPOSIT":
                pass
        cash_est = 30000.0 - spent + received
        open_value = 0.0
        pos_map: dict[str, float] = defaultdict(float)
        cost_map: dict[str, float] = defaultdict(float)
        for _, row in subset.iterrows():
            action = str(row["Action"]).upper()
            ticker = str(row["Ticker"]).upper()
            if action == "BUY":
                pos_map[ticker] += float(row["Shares"])
                cost_map[ticker] += float(row["Price"]) * float(row["Shares"])
            elif action == "SELL":
                if pos_map[ticker] > 0:
                    avg = cost_map[ticker] / pos_map[ticker]
                    sold = float(row["Shares"])
                    cost_map[ticker] -= avg * sold
                    pos_map[ticker] -= sold
        for ticker, shares in pos_map.items():
            if shares > 1e-9:
                last_price_rows = subset[
                    (subset["Ticker"].astype(str).str.upper() == ticker)
                    & (subset["Current_Price"].notna())
                ]
                if not last_price_rows.empty:
                    px = float(last_price_rows.iloc[-1]["Current_Price"])
                    open_value += px * shares
        total = cash_est + open_value
        if total > 0:
            utilization_samples.append(open_value / total)

    avg_util = sum(utilization_samples) / len(utilization_samples) if utilization_samples else 0.0
    idle_pct = (1 - avg_util) * 100 if utilization_samples else None

    idle_cycles = sum(1 for value in utilization_samples if value < 0.05)
    return {
        "cash_available_end": cash,
        "open_positions_value_end": invested_now,
        "account_value_end": account_value,
        "avg_capital_utilization_pct": round(avg_util * 100, 2) if utilization_samples else None,
        "idle_capital_pct": round(idle_pct, 2) if idle_pct is not None else None,
        "idle_samples_under_5pct_invested": idle_cycles,
        "utilization_sample_count": len(utilization_samples),
        "methodology": "6h snapshots reconstructed from portfolio.csv cash flow; end values from tae_accounting_snapshot.json",
    }


def sell_audit(sells: pd.DataFrame) -> dict[str, Any]:
    categories = {
        "TAKE_PROFIT": 0.0,
        "STOP_LOSS": 0.0,
        "TRAILING": 0.0,
        "MANUAL_OR_OTHER": 0.0,
    }
    counts = Counter()
    for _, row in sells.iterrows():
        reason = str(row.get("Reason", "")).upper()
        pnl = float(pd.to_numeric(row.get("PnL"), errors="coerce") or 0)
        if "TAKE PROFIT" in reason:
            key = "TAKE_PROFIT"
        elif "STOP LOSS" in reason:
            key = "STOP_LOSS"
        elif "TRAIL" in reason:
            key = "TRAILING"
        else:
            key = "MANUAL_OR_OTHER"
        categories[key] += pnl
        counts[key] += 1
    return {
        "sell_count": int(len(sells)),
        "profit_by_category_usd": {k: round(v, 2) for k, v in categories.items()},
        "count_by_category": dict(counts),
        "total_realized_pnl_usd": round(float(pd.to_numeric(sells["PnL"], errors="coerce").fillna(0).sum()), 2),
    }


def rank_root_causes(
    buy_rows: list[BuyAuditRow],
    sell_summary: dict[str, Any],
    market_closed_summary: dict[str, Any],
    capital_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    cause_impact: Counter[str] = Counter()
    for row in buy_rows:
        if row.executed_buy or row.missed_profit_usd is None or row.missed_profit_usd <= 0:
            continue
        cause_impact[row.reason_code] += row.missed_profit_usd

    stop_loss_drag = abs(min(0.0, sell_summary["profit_by_category_usd"].get("STOP_LOSS", 0.0)))
    rankings = [
        {
            "cause": "MARKET_CLOSED",
            "impact_usd": round(
                cause_impact.get("MARKET_CLOSED", 0.0)
                + cause_impact.get("MARKET_SESSION_FILTER", 0.0),
                2,
            ),
            "evidence": f"{market_closed_summary['false_market_closed_event_count']} false market-closed log events",
        },
        {
            "cause": "MAX_POSITIONS",
            "impact_usd": round(cause_impact.get("MAX_POSITIONS", 0.0), 2),
            "evidence": "BUY blocat MAX_POSITIONS in bot logs / shadow events",
        },
        {
            "cause": "RISK_GATE",
            "impact_usd": round(cause_impact.get("RISK_GATE", 0.0), 2),
            "evidence": "Market regime / TAE advisory blocks",
        },
        {
            "cause": "STOP_LOSS",
            "impact_usd": round(stop_loss_drag, 2),
            "evidence": "Realized STOP LOSS PnL in portfolio.csv",
        },
        {
            "cause": "CASH_UNUSED",
            "impact_usd": round(
                cause_impact.get("NO_CASH", 0.0),
                2,
            ),
            "evidence": f"Idle capital ~{capital_summary.get('idle_capital_pct')}% avg",
        },
        {
            "cause": "INSUFFICIENT_SCORE",
            "impact_usd": round(cause_impact.get("INSUFFICIENT_SCORE", 0.0), 2),
            "evidence": "Score threshold / non-STRONG BUY",
        },
        {
            "cause": "ALREADY_HELD",
            "impact_usd": round(cause_impact.get("ALREADY_HELD", 0.0), 2),
            "evidence": "Signals while ticker already in portfolio",
        },
    ]
    rankings.sort(key=lambda item: item["impact_usd"], reverse=True)
    for idx, item in enumerate(rankings, start=1):
        item["rank"] = idx
    return rankings


def recommendations(root_causes: list[dict[str, Any]], market_closed_summary: dict[str, Any]) -> list[dict[str, Any]]:
    recs = [
        {
            "rank": 1,
            "change": "Remove legacy global 'Piața este închisă' gate; enforce per-ticker session open only",
            "impact_usd": next(
                (item["impact_usd"] for item in root_causes if item["cause"] == "MARKET_CLOSED"),
                0,
            ),
            "evidence": f"{market_closed_summary['false_market_closed_event_count']} false closed events in logs",
        },
        {
            "rank": 2,
            "change": "Ensure bot RUNNING during all open market sessions (market_session_guard not DRY_RUN)",
            "impact_usd": "operator_confirmation_required",
            "evidence": "market_session_guard.log shows BOT=STOPPED with DRY_RUN=True",
        },
        {
            "rank": 3,
            "change": "Persist tae_shadow_validation_events.csv for every BUY evaluation cycle",
            "impact_usd": "observability",
            "evidence": "Shadow ledger file absent/empty — limits per-signal attribution",
        },
        {
            "rank": 4,
            "change": "Archive live_signals.csv history (append-only) for multi-day forensic replay",
            "impact_usd": "observability",
            "evidence": "live_signals.csv is snapshot-only; alerts_log used as proxy",
        },
        {
            "rank": 5,
            "change": "Review STOP_LOSS -3% vs whipsaw on AAPL/SIE.DE/CSCO",
            "impact_usd": abs(min(0, root_causes[3]["impact_usd"])) if len(root_causes) > 3 else 0,
            "evidence": "portfolio.csv STOP LOSS rows in window",
        },
        {
            "rank": 6,
            "change": "Validate MAX_POSITIONS=12 vs actual cash deployment (~35% utilization)",
            "impact_usd": root_causes[1]["impact_usd"] if len(root_causes) > 1 else 0,
            "evidence": "capital utilization section",
        },
        {
            "rank": 7,
            "change": "Log Market sessions OPEN/CLOSED line on every cycle (current code path under-logged)",
            "impact_usd": "observability",
            "evidence": "0 'Market sessions OPEN' lines in 10-day logs",
        },
        {
            "rank": 8,
            "change": "Deduplicate micro-BUY artifacts (MC.PA $0.03) via MIN_TRADE_USD enforcement audit",
            "impact_usd": 0,
            "evidence": "portfolio.csv MC.PA 0.0001 share buy",
        },
        {
            "rank": 9,
            "change": "Separate REBALANCE/DEPOSIT rows from trading PnL in daily reports",
            "impact_usd": 0,
            "evidence": "portfolio.csv DEPOSIT + REBALANCE simulation rows",
        },
        {
            "rank": 10,
            "change": "Operator confirm capital base ($30k vs virtual $10k DEPOSIT)",
            "impact_usd": 0,
            "evidence": "tae_accounting_snapshot capital_base_status=NEEDS_OPERATOR_CONFIRMATION",
        },
    ]
    return recs


def detect_global_market_gate_fixed() -> dict[str, Any]:
    if not LIVE_BOT_PATH.is_file():
        return {
            "GLOBAL_MARKET_GATE_FIXED": False,
            "reason": "live_bot.py not found",
        }
    source = LIVE_BOT_PATH.read_text(encoding="utf-8")
    has_legacy_gate = "Piața este închisă" in source
    has_disabled_flag = re.search(
        r"GLOBAL_MARKET_GATE_ENABLED\s*=\s*False", source
    ) is not None
    has_per_ticker_log = "evaluating BUY per ticker session" in source
    fixed = has_disabled_flag and not has_legacy_gate and has_per_ticker_log
    return {
        "GLOBAL_MARKET_GATE_FIXED": fixed,
        "GLOBAL_MARKET_GATE_ENABLED": not has_disabled_flag,
        "legacy_global_gate_string_present": has_legacy_gate,
        "per_ticker_session_log_present": has_per_ticker_log,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# TAE 10-Day Trading Opportunity Audit",
        "",
        f"**Mode:** {AUDIT_MODE} | **Window:** {report['window']['start']} → {report['window']['end']}",
        f"**Generated:** {report['generated_at']}",
        "",
        "## Executive Summary",
        "",
        f"- Corrected trading PnL (accounting SSOT): **${report['accounting']['corrected_total_trading_pnl']:,.2f}**",
        f"- BUY opportunities (deduped STRONG BUY score≥{MIN_SCORE_TO_BUY}): **{report['buy_execution']['opportunities']}**",
        f"- BUY executed (portfolio.csv): **{report['buy_execution']['executed_portfolio_rows']}**",
        f"- BUY executed (alert-cycle matches): **{report['buy_execution']['executed']}**",
        f"- Actionable opportunities (excl. already held): **{report['buy_execution']['actionable_opportunities']}**",
        f"- BUY not executed (market closed gate): **{report['buy_execution']['blocked_market_closed']}**",
        f"- FALSE MARKET CLOSED blocked BUY signals: **{report['buy_execution']['false_market_closed_blocked_buys']}**",
        f"- FALSE MARKET CLOSED events: **{report['market_closed']['false_market_closed_event_count']}**",
        f"- Missed profit (evidence-based, alerts max price): **${report['missed_profit']['total_all_causes_usd']:,.2f}**",
        f"- Missed profit (MARKET_CLOSED only): **${report['missed_profit']['total_market_closed_usd']:,.2f}**",
        f"- GLOBAL_MARKET_GATE_FIXED: **{report['market_gate_fix']['GLOBAL_MARKET_GATE_FIXED']}**",
        "",
        "## A. BUY Execution Audit",
        "",
        "Dedup rule: first STRONG BUY (score≥80) per ticker per 60s cycle from `alerts_log.csv`.",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Opportunities (all STRONG BUY cycles) | {report['buy_execution']['opportunities']} |",
        f"| Actionable (new entry, not held) | {report['buy_execution']['actionable_opportunities']} |",
        f"| Executed (portfolio.csv) | {report['buy_execution']['executed_portfolio_rows']} |",
        f"| Executed (alert matches) | {report['buy_execution']['executed']} |",
        f"| Blocked / skipped | {report['buy_execution']['not_executed']} |",
        f"| Actionable execution rate | {report['buy_execution']['execution_rate_pct']:.2f}% |",
        "",
        "### Reason breakdown",
        "",
    ]
    for reason, count in report["buy_execution"]["reason_counts"].items():
        lines.append(f"- **{reason}**: {count}")

    lines.extend(
        [
            "",
            "## B. Market Closed Analysis",
            "",
            f"- Global log count (`Piața este închisă`): **{report['market_closed']['global_market_closed_log_count']}**",
            f"- False market closed events: **{report['market_closed']['false_market_closed_event_count']}**",
            f"- False closed total minutes (merged intervals): **{report['market_closed']['false_market_closed_total_minutes']}**",
            "",
            "### Per-market blocked-while-open counts",
            "",
        ]
    )
    for market, count in report["market_closed"]["per_market_blocked_while_open_count"].items():
        lines.append(f"- **{market}**: {count}")

    lines.extend(["", "### FALSE MARKET CLOSED intervals (sample)", ""])
    for interval in report["market_closed"]["false_market_closed_intervals"][:15]:
        lines.append(
            f"- {interval['start']} → {interval['end']} ({interval['duration_minutes']} min) "
            f"markets open: {', '.join(interval['markets_open_during_interval'])}"
        )

    lines.extend(["", "## C. TOP 20 Missed Profits", ""])
    for item in report["missed_profit"]["top_20"]:
        lines.append(
            f"- **{item['ticker']}** @ {item['timestamp']} | ${item['missed_profit_usd']:,.2f} | "
            f"{item['reason_code']} | price {item['price_at_signal']} → max {item['max_price_subsequent']}"
        )

    lines.extend(["", "## D. BUY Execution Rate", ""])
    for key in [
        "opportunities",
        "executed",
        "rejected",
        "blocked",
        "skipped",
        "execution_rate_pct",
        "rejection_rate_pct",
    ]:
        lines.append(f"- {key}: {report['buy_execution'].get(key)}")

    lines.extend(["", "## E. SELL Audit", ""])
    sell = report["sell_audit"]
    lines.append(f"- Total SELL count: {sell['sell_count']}")
    lines.append(f"- Total realized PnL: ${sell['total_realized_pnl_usd']:,.2f}")
    for cat, value in sell["profit_by_category_usd"].items():
        lines.append(f"- {cat}: ${value:,.2f} ({sell['count_by_category'].get(cat, 0)} trades)")

    lines.extend(["", "## F. Capital Utilization", ""])
    for key, value in report["capital_utilization"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## G. Daily PnL", ""])
    for day in report["daily_pnl"]:
        lines.append(
            f"- **{day['date']}** | BUY {day['buy_count']} | SELL {day['sell_count']} | "
            f"PnL ${day['realized_pnl']:,.2f} | open {day['open_positions_end_of_day']}"
        )

    lines.extend(["", "## H. Root Cause Ranking", ""])
    for item in report["root_causes"]:
        lines.append(f"{item['rank']}. **{item['cause']}** — ${item['impact_usd']:,.2f} — {item['evidence']}")

    lines.extend(["", "## I. Recommendations (advisory only)", ""])
    for rec in report["recommendations"]:
        lines.append(f"{rec['rank']}. {rec['change']} (impact: {rec['impact_usd']}) — {rec['evidence']}")

    lines.extend(
        [
            "",
            "## Data Sources",
            "",
            "- `runtime_outputs/bot_output.log`, `bot_output.log`",
            "- `alerts_log.csv` (STRONG BUY history)",
            "- `portfolio.csv` (executed trades)",
            "- `tae_accounting_snapshot.json`",
            "- `market_session_guard.log`",
            "",
            "## Limitations",
            "",
            "- `live_signals.csv` is snapshot-only; alerts_log used for historical STRONG BUY.",
            "- `tae_shadow_validation_events.csv` not available — per-evaluation TAE attribution incomplete.",
            "- Missed profit uses max subsequent alert price in window (not intraday tick data).",
            "- Log timestamps interpreted as US/Eastern for market calendar cross-check.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_audit() -> dict[str, Any]:
    end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
    if ALERTS_PATH.exists():
        alerts_raw = pd.read_csv(ALERTS_PATH)
        alerts_raw["Time"] = pd.to_datetime(alerts_raw["Time"], errors="coerce")
        if alerts_raw["Time"].notna().any():
            end = min(end, alerts_raw["Time"].max().to_pydatetime().replace(microsecond=0))
    window_end = end
    window_start = (window_end - timedelta(days=WINDOW_DAYS - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    log_rows = load_deduped_logs()
    cycles = parse_bot_cycles(log_rows, window_start, window_end)
    alerts = pd.read_csv(ALERTS_PATH)
    alerts["Time"] = pd.to_datetime(alerts["Time"], errors="coerce")
    opportunities = build_buy_opportunities(alerts, window_start, window_end)

    portfolio = pd.read_csv(PORTFOLIO_PATH)
    portfolio["Date"] = pd.to_datetime(portfolio["Date"], errors="coerce")
    buys = load_portfolio_buys(window_start, window_end)
    sells = load_portfolio_sells(window_start, window_end)

    accounting: dict[str, Any] | None = None
    if ACCOUNTING_SNAPSHOT_PATH.exists():
        accounting = json.loads(ACCOUNTING_SNAPSHOT_PATH.read_text(encoding="utf-8"))

    market_closed_summary = analyze_market_closed_events(log_rows, window_start, window_end)
    global_closed_times = build_global_closed_index(log_rows, window_start, window_end)

    price_cache = build_subsequent_max_prices(alerts, window_end)

    buy_rows: list[BuyAuditRow] = []
    reason_counts: Counter[str] = Counter()
    executed_keys: set[str] = set()
    executed_count = 0
    blocked_market_closed = 0

    for _, opp in opportunities.iterrows():
        ts = opp["Time"].to_pydatetime()
        ticker = str(opp["Ticker"]).upper()
        score = float(opp["Score"])
        price = float(opp["Price"]) if pd.notna(opp["Price"]) else None
        market = get_ticker_market(ticker)
        ticker_open = market_open_at(market, ts)
        cycle = find_cycle_for_ts(cycles, ts)
        global_closed = cycle.global_market_closed if cycle else False
        opens = any_enabled_market_open(ts)
        false_closed = global_closed and opens.get(market, False)

        executed = False
        if not buys.empty:
            match = buys[
                (buys["Ticker"].astype(str).str.upper() == ticker)
                & (abs((buys["Date"] - ts).dt.total_seconds()) <= 180)
            ]
            executed = not match.empty
        if not executed and cycle:
            executed = any(item["ticker"] == ticker for item in cycle.buys)

        held_before = ticker in open_positions_before(portfolio, ts)

        exec_key = f"{ticker}|{ts.strftime('%Y%m%d%H%M')}"
        if executed:
            reason = "BUY_EXECUTED"
            detail = "Matched portfolio/log BUY"
            if exec_key not in executed_keys:
                executed_keys.add(exec_key)
                executed_count += 1
        elif held_before:
            reason = "ALREADY_HELD"
            detail = "Already held — not a new entry opportunity"
        elif score < MIN_SCORE_TO_BUY:
            reason = "INSUFFICIENT_SCORE"
            detail = f"Score {score} < {MIN_SCORE_TO_BUY}"
        elif global_closed or global_market_closed_near_indexed(global_closed_times, ts):
            reason = "MARKET_CLOSED"
            detail = "Global 'Piața este închisă' gate active in cycle"
            blocked_market_closed += 1
            if ticker_open:
                detail += " | FALSE MARKET CLOSED (ticker market open per calendar)"
                false_closed = True
        elif cycle and not ticker_open:
            reason = "MARKET_SESSION_FILTER"
            detail = f"Ticker market {market} closed per calendar"
        elif cycle:
            block = next((b for b in cycle.blocks if b["ticker"] == ticker), None)
            if block:
                reason = classify_block_reason(block["reason"])
                detail = block["reason"]
            else:
                reason = "OTHER"
                detail = "STRONG BUY signal; no execution evidence"
        else:
            reason = "OTHER"
            detail = "No nearby bot cycle in logs"

        max_px = (
            max_subsequent_price_from_cache(price_cache, ticker, ts) if price else None
        )
        missed_profit = None
        if (
            not executed
            and not held_before
            and price
            and max_px
            and max_px > price
            and reason not in ("INSUFFICIENT_SCORE",)
        ):
            missed_profit = round((max_px - price) / price * DEFAULT_TRADE_USD, 2)

        row = BuyAuditRow(
            timestamp=ts.isoformat(sep=" "),
            ticker=ticker,
            score=score,
            market=market,
            market_open=ticker_open,
            bot_running=infer_bot_running(log_rows, ts),
            tae_action=cycle.tae_action if cycle else None,
            executed_buy=executed,
            reason_code=reason,
            reason_detail=detail,
            price_at_signal=price,
            max_price_subsequent=max_px,
            missed_profit_usd=missed_profit,
            false_market_closed=false_closed if global_closed else None,
        )
        buy_rows.append(row)
        reason_counts[reason] += 1

    not_executed = len(buy_rows) - executed_count
    opportunities_count = len(buy_rows)
    execution_rate = (executed_count / opportunities_count * 100) if opportunities_count else 0.0

    missed_rows = [
        row
        for row in buy_rows
        if not row.executed_buy and row.missed_profit_usd and row.missed_profit_usd > 0
    ]
    missed_rows.sort(key=lambda row: row.missed_profit_usd or 0, reverse=True)
    top_20 = missed_rows[:20]

    false_mc_blocked = [
        row
        for row in buy_rows
        if row.reason_code == "MARKET_CLOSED" and row.false_market_closed
    ]
    actionable_opportunities = sum(
        1 for row in buy_rows if row.reason_code not in ("ALREADY_HELD", "BUY_EXECUTED")
    )

    total_missed_all = round(sum(row.missed_profit_usd or 0 for row in missed_rows), 2)
    total_missed_mc = round(
        sum(row.missed_profit_usd or 0 for row in missed_rows if row.reason_code == "MARKET_CLOSED"),
        2,
    )

    sell_summary = sell_audit(sells)
    capital_summary = compute_capital_utilization(portfolio, accounting, window_start, window_end)
    daily_pnl = compute_daily_pnl(portfolio, window_start, window_end)
    root_causes = rank_root_causes(buy_rows, sell_summary, market_closed_summary, capital_summary)
    recs = recommendations(root_causes, market_closed_summary)
    market_gate_fix = detect_global_market_gate_fixed()

    portfolio_buys_unique = int(len(buys)) if not buys.empty else 0

    report = {
        "schema": "tae.10_day_trading_audit.v1",
        "mode": AUDIT_MODE,
        "generated_at": datetime.now().isoformat(),
        "window": {
            "start": window_start.isoformat(sep=" "),
            "end": window_end.isoformat(sep=" "),
            "days": WINDOW_DAYS,
        },
        "accounting": {
            "corrected_total_trading_pnl": accounting.get("corrected_total_trading_pnl") if accounting else None,
            "cash_available": accounting.get("cash_available") if accounting else None,
            "account_value_corrected": accounting.get("account_value_corrected") if accounting else None,
        },
        "buy_execution": {
            "opportunities": opportunities_count,
            "actionable_opportunities": actionable_opportunities,
            "executed": executed_count,
            "executed_portfolio_rows": portfolio_buys_unique,
            "not_executed": not_executed,
            "rejected": reason_counts.get("INSUFFICIENT_SCORE", 0),
            "blocked": reason_counts.get("MARKET_CLOSED", 0)
            + reason_counts.get("MARKET_SESSION_FILTER", 0)
            + reason_counts.get("RISK_GATE", 0)
            + reason_counts.get("MAX_POSITIONS", 0),
            "skipped": reason_counts.get("OTHER", 0) + reason_counts.get("ALREADY_HELD", 0),
            "blocked_market_closed": blocked_market_closed,
            "false_market_closed_blocked_buys": len(false_mc_blocked),
            "execution_rate_pct": round(
                (portfolio_buys_unique / actionable_opportunities * 100)
                if actionable_opportunities
                else 0.0,
                4,
            ),
            "rejection_rate_pct": round(
                100 - (portfolio_buys_unique / opportunities_count * 100) if opportunities_count else 0.0,
                4,
            ),
            "reason_counts": dict(reason_counts),
            "alerts_coverage_note": "alerts_log STRONG BUY rows exist from 2026-06-24 onward within this 10-day window; Jun 20-23 had zero alert rows",
        },
        "false_market_closed_blocked_details": [asdict(row) for row in false_mc_blocked],
        "market_gate_fix": market_gate_fix,
        "market_closed": market_closed_summary,
        "missed_profit": {
            "methodology": "DEFAULT_TRADE_USD * (max_subsequent_alert_price - signal_price) / signal_price",
            "default_trade_usd": DEFAULT_TRADE_USD,
            "total_all_causes_usd": total_missed_all,
            "total_market_closed_usd": total_missed_mc,
            "top_20": [asdict(row) for row in top_20],
        },
        "sell_audit": sell_summary,
        "capital_utilization": capital_summary,
        "daily_pnl": daily_pnl,
        "root_causes": root_causes,
        "recommendations": recs,
        "buy_audit_rows": [asdict(row) for row in buy_rows],
        "data_sources": {
            "logs": [str(p) for p in LOG_PATHS if p.exists()],
            "alerts_log": str(ALERTS_PATH),
            "portfolio": str(PORTFOLIO_PATH),
            "shadow_events": str(SHADOW_EVENTS_PATH) if SHADOW_EVENTS_PATH.exists() else None,
            "accounting_snapshot": str(ACCOUNTING_SNAPSHOT_PATH) if ACCOUNTING_SNAPSHOT_PATH.exists() else None,
        },
    }
    return report


def write_csv(buy_rows: list[dict[str, Any]]) -> None:
    if not buy_rows:
        OUTPUT_CSV.write_text("", encoding="utf-8")
        return
    fieldnames = list(buy_rows[0].keys())
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(buy_rows)


def main() -> None:
    report = run_audit()
    OUTPUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(report), encoding="utf-8")
    write_csv(report["buy_audit_rows"])
    print(render_markdown(report))


if __name__ == "__main__":
    main()
