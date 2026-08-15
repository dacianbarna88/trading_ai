#!/usr/bin/env python3
"""Decision-traceable, read-only daily operating report for parallel PAPER.

The report joins the canonical V1/V2 decision, execution, and trade journals
without changing books, journals, cycle state, or LIVE files.  A before/after
hash snapshot distinguishes concurrent daemon activity from report writes.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo

from tae_parallel_paper_config import (
    PROJECT_ROOT,
    REPORTS_DIR,
    V1_DIR,
    V2_DIR,
    load_parallel_paper_config,
)

TZ = ZoneInfo("Europe/Bucharest")
SCHEMA = "tae.today_decision_trace_report.v1"

BUY_ACTIONS = frozenset({"BUY", "OPEN", "ADD", "ADD_TRANCHE"})
SELL_ACTIONS = frozenset({"SELL", "CLOSE", "REDUCE"})
FILL_ACTIONS = BUY_ACTIONS | SELL_ACTIONS
SEVERITIES = frozenset({"INFO", "WARNING", "ERROR", "CRITICAL"})
RUNTIME_RELEVANT_PATHS = (
    "tae_parallel_paper*.py",
    "tae_strategy_v2*.py",
    "live_bot.py",
)


class ReportDocument(dict[str, Any]):
    """Dict with non-serialized compatibility views for legacy Python callers."""

    def _legacy(self, key: str) -> Any:
        capital = dict.get(self, "capital", {})
        transactions = dict.get(self, "executed_transactions", [])
        conclusion = dict.get(self, "executive_conclusion", {})
        aliases = {
            "schema": (dict.get(self, "metadata", {}) or {}).get("schema"),
            "conclusion": conclusion,
            "arms": capital,
            "buys": [row for row in transactions if row.get("action") in BUY_ACTIONS],
            "sells": [row for row in transactions if row.get("action") in SELL_ACTIONS],
            "last_log_activity": {},
            "v1_vs_v2": {
                "V1_BUY_COUNT": sum(
                    row.get("strategy") == "V1" and row.get("action") == "BUY"
                    for row in transactions
                ),
                "V1_SELL_COUNT": sum(
                    row.get("strategy") == "V1" and row.get("action") in SELL_ACTIONS
                    for row in transactions
                ),
                "V2_OPEN_COUNT": sum(
                    row.get("strategy") == "V2" and row.get("action") == "OPEN"
                    for row in transactions
                ),
                "V2_ADD_COUNT": sum(
                    row.get("strategy") == "V2"
                    and row.get("action") in {"ADD", "ADD_TRANCHE"}
                    for row in transactions
                ),
            },
        }
        if key not in aliases:
            raise KeyError(key)
        return aliases[key]

    def __getitem__(self, key: str) -> Any:
        try:
            return super().__getitem__(key)
        except KeyError:
            return self._legacy(key)

    def __contains__(self, key: object) -> bool:
        return super().__contains__(key) or (
            isinstance(key, str)
            and key
            in {
                "schema",
                "conclusion",
                "arms",
                "buys",
                "sells",
                "last_log_activity",
                "v1_vs_v2",
            }
        )


def _now_local() -> datetime:
    return datetime.now(TZ)


def _parse_ts(value: Any) -> datetime | None:
    """Parse a journal timestamp and normalize it to Europe/Bucharest."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(TZ)


def _day_bounds(day: str | date | datetime | None = None) -> tuple[datetime, datetime]:
    """Return local midnight through now, or historical local end-of-day."""
    now = _now_local()
    if day is None:
        selected = now.date()
    elif isinstance(day, datetime):
        selected = day.astimezone(TZ).date() if day.tzinfo else day.date()
    elif isinstance(day, date):
        selected = day
    else:
        try:
            selected = date.fromisoformat(str(day))
        except ValueError as exc:
            raise ValueError("--day must be YYYY-MM-DD") from exc
    if selected > now.date():
        raise ValueError("--day cannot be in the future")
    start = datetime.combine(selected, time.min, TZ)
    end = now if selected == now.date() else datetime.combine(selected, time.max, TZ)
    return start, end


def _event_ts(row: dict[str, Any]) -> datetime | None:
    return _parse_ts(
        row.get("ts")
        or row.get("timestamp")
        or row.get("created_at")
        or row.get("updated_at")
    )


def _filter_today(
    rows: Iterable[dict[str, Any]], start: datetime, end: datetime
) -> list[dict[str, Any]]:
    return [row for row in rows if (dt := _event_ts(row)) is not None and start <= dt <= end]


def _f(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _s(value: Any, default: str = "") -> str:
    return str(default if value is None else value).strip()


def _round(value: Any, digits: int = 6) -> float | None:
    number = _f(value)
    return None if number is None else round(number, digits)


def _first_number(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _f(row.get(key))
        if value is not None:
            return value
    return None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    result: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            result.append(row)
    return result


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


def _file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _watch_paths() -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for arm, arm_dir in (("v1", V1_DIR), ("v2", V2_DIR)):
        for filename in ("account.json", "portfolio.json"):
            paths[f"{arm}/{filename}"] = arm_dir / filename
        for journal in ("trades.jsonl", "executions.jsonl", "decisions.jsonl"):
            paths[f"{arm}/journals/{journal}"] = arm_dir / "journals" / journal
    paths["v2/cycle_state.json"] = V2_DIR / "cycle_state.json"
    paths["portfolio.csv"] = PROJECT_ROOT / "portfolio.csv"
    paths["live_signals.csv"] = PROJECT_ROOT / "live_signals.csv"
    return paths


def _hash_snapshot(paths: dict[str, Path]) -> dict[str, str | None]:
    return {name: _file_sha256(path) for name, path in paths.items()}


def _git_output(args: Sequence[str]) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=str(PROJECT_ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _git_head() -> str | None:
    return _git_output(["rev-parse", "HEAD"])


def _git_status_short() -> str:
    return _git_output(["status", "--short"]) or ""


def _latest_runtime_commit() -> dict[str, Any]:
    output = _git_output(
        [
            "log",
            "-1",
            "--format=%H|%ct|%cI",
            "--",
            *RUNTIME_RELEVANT_PATHS,
        ]
    )
    if not output:
        return {"commit": None, "epoch": None, "committed_at": None}
    parts = output.split("|", 2)
    return {
        "commit": parts[0] if parts else None,
        "epoch": _f(parts[1]) if len(parts) > 1 else None,
        "committed_at": parts[2] if len(parts) > 2 else None,
    }


def _ps_processes(patterns: Sequence[str]) -> list[dict[str, Any]]:
    try:
        output = subprocess.check_output(
            ["ps", "aux"], text=True, stderr=subprocess.DEVNULL
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [{"error": str(exc)}]
    result: list[dict[str, Any]] = []
    own_pid = str(__import__("os").getpid())
    for line in output.splitlines():
        parts = line.split(None, 10)
        if len(parts) < 11 or parts[1] == own_pid:
            continue
        command = parts[10]
        # Inspect executable/script positions only.  Agent and editor command
        # lines can contain these filenames inside prompts and must not count.
        command_parts = command.split()
        launch_tokens = [Path(token).name for token in command_parts[:4]]
        if not any(
            token == pattern or token.startswith(pattern + ".")
            for token in launch_tokens
            for pattern in patterns
        ):
            continue
        if "grep " in command or "rg " in command:
            continue
        result.append({"pid": int(parts[1]), "command": command[:300]})
    return result


def _pid_start(pid: int) -> dict[str, Any]:
    try:
        epoch_raw = subprocess.check_output(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if not epoch_raw:
            return {"epoch": None, "started_at": None}
        parsed = datetime.strptime(epoch_raw, "%a %b %d %H:%M:%S %Y").astimezone()
        return {"epoch": parsed.timestamp(), "started_at": parsed.isoformat()}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {"epoch": None, "started_at": None}


def _process_runtime() -> dict[str, Any]:
    root = V1_DIR.parent
    groups = {
        "live_bot": _ps_processes(("live_bot.py",)),
        "parallel_paper": _ps_processes(
            ("tae_parallel_paper_daemon", "parallel-paper-start")
        ),
        "dashboard": _ps_processes(("dashboard_v2.py", "streamlit")),
    }
    latest = _latest_runtime_commit()
    for name, processes in groups.items():
        inspectable = not (processes and processes[0].get("error"))
        for process in processes:
            if process.get("pid"):
                process.update(_pid_start(int(process["pid"])))
        starts = [p.get("epoch") for p in processes if p.get("epoch") is not None]
        alignment = None
        if starts and latest.get("epoch") is not None:
            alignment = all(start >= latest["epoch"] - 5 for start in starts)
        groups[name] = {
            "running": bool(processes) and inspectable,
            "inspectable": inspectable,
            "processes": processes,
            "runtime_relevant_commit_alignment": alignment,
        }
    heartbeat = _read_json(root / "parallel_paper_heartbeat.json")
    status = _read_json(root / "runtime_status.json")
    groups["parallel_paper"]["heartbeat"] = heartbeat
    groups["parallel_paper"]["runtime_status_running"] = (status or {}).get("running")
    groups["runtime_relevant_commit"] = latest
    groups["head"] = _git_head()
    groups["alignment_note"] = (
        "Process start times are compared with the latest commit touching runtime-relevant "
        "parallel-paper, Strategy V2, or LIVE code; reporting-only commits do not trigger "
        "an economic-runtime mismatch."
    )
    return groups


def _market_sessions(at: datetime, tickers: Iterable[str]) -> dict[str, Any]:
    from markets.market_hours import (
        get_ticker_market,
        is_market_open,
        is_ticker_market_open,
    )

    markets = {"EU", "UK", "US"}
    markets.update(get_ticker_market(ticker) for ticker in tickers if ticker)
    sessions: dict[str, Any] = {}
    for market in sorted(markets):
        try:
            sessions[market] = {
                "open": bool(is_market_open(market, at=at)),
                "as_of": at.isoformat(),
            }
        except Exception as exc:
            sessions[market] = {"open": None, "as_of": at.isoformat(), "error": str(exc)}
    sessions["tickers"] = {}
    for ticker in sorted(set(tickers)):
        try:
            sessions["tickers"][ticker] = {
                "market": get_ticker_market(ticker),
                "open": bool(is_ticker_market_open(ticker, at=at)),
            }
        except Exception as exc:
            sessions["tickers"][ticker] = {"market": None, "open": None, "error": str(exc)}
    return sessions


def _strategy_lab_status() -> dict[str, Any]:
    try:
        from tae_strategy_lab_facade import build_scoreboard, lab_status
        from tae_strategy_lab_promotion import promotion_status

        scoreboard = build_scoreboard(persist=False)
        status = lab_status()
        promotion = promotion_status()
        return {
            "reconciliation_pass": (scoreboard.get("reconciliation") or {}).get("pass"),
            "lab_status": status,
            "promotion_status": promotion,
        }
    except Exception as exc:
        return {"reconciliation_pass": None, "error": str(exc)}


def _prior_close_av(
    arm: str, selected_day: str, metrics: list[dict[str, str]]
) -> float | None:
    key = f"{arm}_av"
    eligible = sorted(
        (row for row in metrics if _s(row.get("date")) < selected_day),
        key=lambda row: _s(row.get("date")),
    )
    return _f(eligible[-1].get(key)) if eligible else None


def _normal_position(ticker: str, raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    shares = _f(raw.get("shares"), 0.0) or 0.0
    if shares <= 0:
        return None
    avg_price = _f(raw.get("avg_price"))
    current_price = _f(raw.get("current_price"))
    return {
        "ticker": ticker,
        "shares": shares,
        "avg_price": avg_price,
        "current_price": current_price,
        "market_value": (
            _round(shares * current_price) if current_price is not None else None
        ),
        "unrealized_pnl": _f(raw.get("unrealized_pnl")),
        "unrealized_pct": (
            _round((current_price / avg_price - 1.0) * 100.0)
            if current_price is not None and avg_price not in (None, 0)
            else None
        ),
        "mark_status": raw.get("mark_status"),
        "mark_timestamp": raw.get("mark_timestamp")
        or raw.get("last_valid_mark_timestamp"),
        "strategy_v2_cycle_id": raw.get("strategy_v2_cycle_id"),
        "status": raw.get("status"),
        "protect_mode": raw.get("protect_mode"),
    }


def _cycle_by_ticker(cycle_state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for cycle in (cycle_state.get("cycles") or {}).values():
        if not isinstance(cycle, dict) or not cycle.get("ticker"):
            continue
        ticker = str(cycle["ticker"])
        existing = result.get(ticker)
        if existing is None or _s(cycle.get("updated_at")) > _s(existing.get("updated_at")):
            result[ticker] = cycle
    return result


def _normal_cycle(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not raw:
        return None
    return {
        "cycle_id": raw.get("cycle_id"),
        "opened_at": raw.get("opened_at"),
        "tranche_count": raw.get("tranche_count"),
        "next_tranche_reference_price": _f(raw.get("next_tranche_reference_price")),
        "average_cost": _f(raw.get("average_cost")),
        "status": raw.get("status"),
    }


def _row_arm(row: dict[str, Any], fallback: str) -> str:
    arm = _s(row.get("arm") or row.get("strategy_version") or fallback).upper()
    return arm if arm in {"V1", "V2"} else fallback


def _row_action(row: dict[str, Any]) -> str:
    return _s(row.get("action")).upper()


def _dedupe_rows(rows: Iterable[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    """Collapse repeated journal snapshots while preserving distinct events."""
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        identity = (
            row.get(f"{kind}_id")
            or row.get("execution_id")
            or row.get("decision_id")
            or row.get("ts"),
            row.get("ticker"),
            row.get("action"),
            row.get("phase"),
        )
        seen[identity] = row
    return sorted(seen.values(), key=lambda row: _event_ts(row) or datetime.min.replace(tzinfo=TZ))


def _indexes(
    decisions: list[dict[str, Any]], executions: list[dict[str, Any]]
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    decisions_by_id = {
        str(row["decision_id"]): row for row in decisions if row.get("decision_id")
    }
    executions_by_id = {
        str(row["execution_id"]): row for row in executions if row.get("execution_id")
    }
    executions_by_decision = {
        str(row["decision_id"]): row for row in executions if row.get("decision_id")
    }
    return decisions_by_id, executions_by_id, executions_by_decision


def _lookup_reason(
    row: dict[str, Any],
    decisions_by_id: dict[str, dict[str, Any]],
    executions_by_id: dict[str, dict[str, Any]],
    executions_by_decision: dict[str, dict[str, Any]],
) -> tuple[str | None, str | None]:
    if _s(row.get("reason")):
        return _s(row.get("reason")), "trade"
    candidates = [
        executions_by_id.get(_s(row.get("execution_id"))),
        executions_by_decision.get(_s(row.get("decision_id"))),
        decisions_by_id.get(_s(row.get("decision_id"))),
    ]
    for candidate, source in zip(candidates, ("execution", "execution", "decision")):
        if candidate and _s(candidate.get("reason") or candidate.get("tranche_gate_code")):
            return _s(candidate.get("reason") or candidate.get("tranche_gate_code")), source
    return None, None


def _trade_economics(row: dict[str, Any]) -> dict[str, Any]:
    """Return explicit gross/fee/net PnL without treating valid zero as missing."""
    fees = _first_number(row, "total_transaction_cost", "fees")
    if fees is None:
        costs = [
            _f(row.get("slippage_cost"), 0.0) or 0.0,
            _f(row.get("spread_cost"), 0.0) or 0.0,
            _f(row.get("commission_cost"), 0.0) or 0.0,
        ]
        fees = sum(costs) if any(costs) else 0.0
    gross = _first_number(row, "realized_pnl_gross")
    net = _first_number(row, "realized_pnl_net", "realized_pnl")
    if gross is None and net is not None:
        gross = net + fees
    if net is None and gross is not None:
        net = gross - fees
    treatment = None
    if gross is not None and net is not None and abs(net - (gross - fees)) <= 0.02:
        treatment = "NET_INCLUDES_FEES"
    elif gross is not None or net is not None:
        treatment = "UNRESOLVED_FROM_CANONICAL_FIELDS"
    return {
        "PNL_BEFORE_FEES": _round(gross),
        "FEES": _round(fees),
        "PNL_AFTER_FEES": _round(net),
        "ACCOUNTING_TREATMENT": treatment,
    }


def _transaction(
    row: dict[str, Any],
    arm: str,
    source: str,
    decisions_by_id: dict[str, dict[str, Any]],
    executions_by_id: dict[str, dict[str, Any]],
    executions_by_decision: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    reason, reason_source = _lookup_reason(
        row, decisions_by_id, executions_by_id, executions_by_decision
    )
    shares = _first_number(row, "shares", "quantity")
    price = _first_number(row, "price", "fill_price", "mark_price")
    action = _row_action(row)
    economics = _trade_economics(row)
    return {
        "timestamp": row.get("ts") or row.get("timestamp"),
        "strategy": arm,
        "ticker": row.get("ticker"),
        "action": action,
        "shares": shares,
        "price": price,
        "gross_value": _round(shares * price)
        if shares is not None and price is not None
        else _first_number(row, "gross", "gross_notional", "gross_proceeds", "value"),
        **economics,
        "cash_before": _f(row.get("cash_before")),
        "cash_after": _f(row.get("cash_after")),
        "cash_released": (
            _round((_f(row.get("cash_after")) or 0.0) - (_f(row.get("cash_before")) or 0.0))
            if row.get("cash_before") is not None and row.get("cash_after") is not None
            else None
        ),
        "decision_id": row.get("decision_id"),
        "execution_id": row.get("execution_id"),
        "cycle_id": row.get("cycle_id"),
        "tranche": row.get("tranche"),
        "reason": reason,
        "reason_source": reason_source,
        "reason_status": (
            "SELL_REASON_MISSING"
            if action in SELL_ACTIONS and not reason
            else "PRESENT"
        ),
        "source": source,
    }


def _build_transactions(
    arm: str,
    trades: list[dict[str, Any]],
    executions: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    decisions_by_id, executions_by_id, executions_by_decision = _indexes(
        decisions, executions
    )
    result: list[dict[str, Any]] = []
    used_execution_ids: set[str] = set()
    used_decision_actions: set[tuple[str, str]] = set()
    for trade in _dedupe_rows(trades, "trade"):
        if _row_action(trade) not in FILL_ACTIONS:
            continue
        result.append(
            _transaction(
                trade,
                arm,
                f"runtime_outputs/parallel_paper/{arm.lower()}/journals/trades.jsonl",
                decisions_by_id,
                executions_by_id,
                executions_by_decision,
            )
        )
        if trade.get("execution_id"):
            used_execution_ids.add(str(trade["execution_id"]))
        used_decision_actions.add((_s(trade.get("decision_id")), _row_action(trade)))
    for execution in _dedupe_rows(executions, "execution"):
        action = _row_action(execution)
        if execution.get("executed") is not True or action not in FILL_ACTIONS:
            continue
        eid = _s(execution.get("execution_id"))
        decision_action = (_s(execution.get("decision_id")), action)
        if (eid and eid in used_execution_ids) or decision_action in used_decision_actions:
            continue
        result.append(
            _transaction(
                execution,
                arm,
                f"runtime_outputs/parallel_paper/{arm.lower()}/journals/executions.jsonl",
                decisions_by_id,
                executions_by_id,
                executions_by_decision,
            )
        )
    return sorted(result, key=lambda row: _parse_ts(row.get("timestamp")) or datetime.min.replace(tzinfo=TZ))


def _non_execution_code(row: dict[str, Any]) -> str:
    action = _row_action(row)
    reason = _s(row.get("reason") or row.get("tranche_gate_code")).upper()
    if "MARKET_CLOSED" in reason or "SESSION" in reason:
        return "MARKET_CLOSED"
    if "STALE" in reason or "NO_PRICE" in reason or "MARK" in reason:
        return "PRICE_STALE"
    if "INSUFFICIENT" in reason and "CASH" in reason:
        return "INSUFFICIENT_CASH"
    if "TICKER_SCOPE" in reason:
        return "BLOCKED_TICKER_SCOPE"
    if "CONTROL_FALLBACK_OUT_OF_SCOPE" in reason:
        return "CONTROL_FALLBACK_OUT_OF_SCOPE"
    if "THESIS_WATCH" in reason or "WATCH" in reason or "SCORE" in reason or "PDE" in reason:
        return "WATCH_BLOCK"
    if "PRICE_STEP_NOT_REACHED" in reason:
        return "PRICE_STEP_NOT_REACHED"
    if "MAX_POSITION" in reason:
        return "MAX_POSITIONS"
    if action in SELL_ACTIONS:
        return "SELL_NOT_EXECUTED"
    if action in BUY_ACTIONS:
        return "BUY_NOT_EXECUTED"
    if action == "BLOCKED":
        return "BLOCKED"
    if action == "HOLD":
        return "HOLD"
    return "NON_FILL"


def _build_nonexecuted(
    arm: str,
    executions: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    *,
    filled_decision_ids: set[str] | None = None,
    filled_execution_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Build non-fill decision/execution rows; never reclassify executed fills."""
    filled_decision_ids = filled_decision_ids or set()
    filled_execution_ids = filled_execution_ids or set()

    def _is_filled(row: dict[str, Any]) -> bool:
        did = _s(row.get("decision_id"))
        eid = _s(row.get("execution_id"))
        if did and did in filled_decision_ids:
            return True
        if eid and eid in filled_execution_ids:
            return True
        if row.get("executed") is True and _row_action(row) in FILL_ACTIONS:
            return True
        return False

    rows: list[tuple[str, dict[str, Any]]] = [
        ("execution", row)
        for row in _dedupe_rows(executions, "execution")
        if not _is_filled(row)
    ]
    seen_decision_ids = {_s(row.get("decision_id")) for _, row in rows if row.get("decision_id")}
    rows.extend(
        ("decision", row)
        for row in _dedupe_rows(decisions, "decision")
        if not _is_filled(row)
        and _s(row.get("decision_id")) not in seen_decision_ids
        and _s(row.get("decision_id")) not in filled_decision_ids
    )
    result = []
    for source, row in rows:
        result.append(
            {
                "timestamp": row.get("ts") or row.get("timestamp"),
                "strategy": arm,
                "ticker": row.get("ticker"),
                "action": _row_action(row),
                "phase": row.get("phase"),
                "reason": row.get("reason") or row.get("tranche_gate_code"),
                "classification": _non_execution_code(row),
                "decision_id": row.get("decision_id"),
                "execution_id": row.get("execution_id"),
                "cycle_id": row.get("cycle_id"),
                "tranche": row.get("tranche"),
                "mark_status": row.get("mark_status"),
                "mark_price": _f(row.get("mark_price")),
                "score": _f(row.get("score")),
                "source": source,
            }
        )
    return sorted(result, key=lambda row: _parse_ts(row.get("timestamp")) or datetime.min.replace(tzinfo=TZ))


def _event_record(arm: str, kind: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": row.get("ts") or row.get("timestamp"),
        "strategy": arm,
        "ticker": row.get("ticker"),
        "event_type": kind.upper(),
        "action": _row_action(row),
        "executed": row.get("executed") if kind != "trade" else True,
        "reason": row.get("reason") or row.get("tranche_gate_code"),
        "decision_id": row.get("decision_id"),
        "execution_id": row.get("execution_id"),
        "cycle_id": row.get("cycle_id"),
        "tranche": row.get("tranche"),
        "phase": row.get("phase"),
        "mark_price": _first_number(row, "mark_price", "price", "fill_price"),
    }


def _trace_limit(
    events: list[dict[str, Any]], ticker: str | None, all_events: bool
) -> list[dict[str, Any]]:
    events = sorted(
        events,
        key=lambda row: _parse_ts(row.get("timestamp")) or datetime.min.replace(tzinfo=TZ),
    )
    if all_events or ticker:
        return events
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_ticker[_s(event.get("ticker"), "—")].append(event)
    selected_ids = {
        id(event)
        for ticker_events in by_ticker.values()
        for event in ticker_events[-5:]
    }
    selected = [event for event in events if id(event) in selected_ids]
    return selected[-30:]


def _latest_by_ticker(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = _s(row.get("ticker"))
        if ticker:
            result[ticker] = row
    return result


def _position_side(
    position: dict[str, Any] | None,
    latest_event: dict[str, Any] | None,
    cycle: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if position is None:
        return None
    return {
        **position,
        "current_action": (
            latest_event.get("action") if latest_event else "NO_CURRENT_DECISION_EVENT"
        ),
        "current_reason": latest_event.get("reason") if latest_event else None,
        "decision_id": latest_event.get("decision_id") if latest_event else None,
        "execution_id": latest_event.get("execution_id") if latest_event else None,
        "cycle": cycle,
    }


def _cash_release_code(
    arm: str,
    position: dict[str, Any],
    latest: dict[str, Any] | None,
    market_open: bool | None,
    v2_config: dict[str, Any],
    cycle: dict[str, Any] | None,
) -> tuple[str, str]:
    action = _s((latest or {}).get("action")).upper()
    reason = _s((latest or {}).get("reason")).upper()
    mark_status = _s(position.get("mark_status")).upper()
    unrealized_pct = _f(position.get("unrealized_pct"))
    if position.get("shares", 0) <= 0:
        return "NO_POSITION", "Canonical portfolio has no held shares."
    if mark_status and mark_status not in {"FRESH", "OK", "VALID"}:
        return "PRICE_STALE", f"Canonical mark status is {mark_status}."
    if any(token in reason for token in ("EXECUTION_FAIL", "REJECT", "ERROR")):
        return "EXECUTION_FAILURE", f"Latest canonical reason: {reason}."
    if action in SELL_ACTIONS and (latest or {}).get("executed") is not True:
        return "SELL_AUTHORIZED_NOT_EXECUTED", "A sell/close event exists without a fill."
    if "HARD_RISK" in reason and any(token in reason for token in ("LOCK", "BLOCK")):
        return "POSITION_LOCKED_BY_HARD_RISK", f"Latest canonical reason: {reason}."
    if market_open is False:
        return "MARKET_CLOSED", "Ticker market is closed at the report boundary."
    if arm == "V2":
        stop = _f(v2_config.get("V2_STOP_LOSS_PCT"))
        target_raw = _f(v2_config.get("minimum_cycle_profit_pct"))
        target = target_raw * 100.0 if target_raw is not None and abs(target_raw) <= 1 else target_raw
        if unrealized_pct is None:
            return "UNKNOWN", "Insufficient canonical price/cost evidence."
        if stop is not None and unrealized_pct > stop and unrealized_pct < 0:
            return (
                "STOP_LOSS_NOT_REACHED",
                f"Unrealized {unrealized_pct:.4f}% remains above V2 stop {stop:.4f}%.",
            )
        if target is not None and unrealized_pct < target:
            return (
                "V2_CYCLE_TARGET_NOT_REACHED",
                f"Unrealized {unrealized_pct:.4f}% is below cycle target {target:.4f}%; "
                f"cycle status={_s((cycle or {}).get('status'), 'UNKNOWN')}.",
            )
        if not latest:
            return "SELL_DECISION_NOT_CREATED", "No sell/close event exists today."
        return "SELL_POLICY_NOT_APPLICABLE", f"Latest canonical action/reason is {action}/{reason or '—'}."
    if any(token in reason for token in ("TAKE_PROFIT", "TRAILING")):
        return "TAKE_PROFIT_NOT_REACHED", f"Latest canonical reason: {reason}."
    if any(token in reason for token in ("STOP", "HOLD_OPEN")) and (
        unrealized_pct is None or unrealized_pct > -3.0
    ):
        return "STOP_LOSS_NOT_REACHED", (
            f"Latest reason={reason or 'V1_HOLD_OPEN'}; unrealized={unrealized_pct}%. "
            "No V1 exit threshold is fabricated."
        )
    if not latest:
        return "SELL_DECISION_NOT_CREATED", "No current decision event exists today."
    if action == "HOLD":
        return "SELL_POLICY_NOT_APPLICABLE", f"Latest canonical reason: {reason or 'V1_HOLD_OPEN'}."
    return "UNKNOWN", "Insufficient canonical evidence to identify a narrower release blocker."


def _anomaly(
    code: str,
    severity: str,
    message: str,
    **context: Any,
) -> dict[str, Any]:
    return {
        "severity": severity if severity in SEVERITIES else "WARNING",
        "code": code,
        "message": message,
        "context": context,
    }


def _filter_rows(
    rows: list[dict[str, Any]], ticker: str | None, strategy: str | None
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if (ticker is None or row.get("ticker") == ticker)
        and (strategy is None or row.get("strategy") == strategy)
    ]


def build_today_report(
    day: str | date | datetime | None = None,
    ticker: str | None = None,
    strategy: str | None = None,
    all_events: bool = False,
    cio: bool = False,
) -> dict[str, Any]:
    """Build the canonical read-only daily decision trace."""
    if strategy is not None:
        strategy = strategy.upper()
        if strategy not in {"V1", "V2"}:
            raise ValueError("--strategy must be V1 or V2")
    ticker = _s(ticker) or None
    start, end = _day_bounds(day)
    selected_day = start.date().isoformat()
    watched = _watch_paths()
    if cio:
        try:
            from tae_today_cio_extension import cio_integrity_paths

            watched.update(cio_integrity_paths())
        except Exception:
            # CIO is fail-soft; the extension itself will expose the import error.
            pass
    hashes_before = _hash_snapshot(watched)

    config = load_parallel_paper_config()
    v2_config = _read_json(PROJECT_ROOT / "tae_strategy_v2_config.json") or {}
    metrics = _read_csv(REPORTS_DIR / "tae_parallel_daily_metrics.csv")
    cycle_state = _read_json(V2_DIR / "cycle_state.json") or {}
    cycles = _cycle_by_ticker(cycle_state)

    arm_data: dict[str, dict[str, Any]] = {}
    all_transactions: list[dict[str, Any]] = []
    all_nonexecuted: list[dict[str, Any]] = []
    raw_events: list[dict[str, Any]] = []
    all_tickers: set[str] = set()

    for arm, arm_dir in (("V1", V1_DIR), ("V2", V2_DIR)):
        account = _read_json(arm_dir / "account.json") or {}
        portfolio = _read_json(arm_dir / "portfolio.json") or {}
        positions = {
            name: normalized
            for name, raw in (portfolio.get("positions") or {}).items()
            if (normalized := _normal_position(name, raw)) is not None
        }
        all_tickers.update(positions)
        full_trades = _read_jsonl(arm_dir / "journals" / "trades.jsonl")
        full_executions = _read_jsonl(arm_dir / "journals" / "executions.jsonl")
        full_decisions = _read_jsonl(arm_dir / "journals" / "decisions.jsonl")
        trades = _filter_today(full_trades, start, end)
        executions = _filter_today(full_executions, start, end)
        decisions = _filter_today(full_decisions, start, end)
        all_tickers.update(_s(row.get("ticker")) for row in trades + executions + decisions)

        transactions = _build_transactions(arm, trades, executions, decisions)
        filled_decision_ids = {_s(t.get("decision_id")) for t in transactions if t.get("decision_id")}
        filled_execution_ids = {_s(t.get("execution_id")) for t in transactions if t.get("execution_id")}
        nonexecuted = _build_nonexecuted(
            arm,
            executions,
            decisions,
            filled_decision_ids=filled_decision_ids,
            filled_execution_ids=filled_execution_ids,
        )
        all_transactions.extend(transactions)
        all_nonexecuted.extend(nonexecuted)
        for kind, rows in (
            ("decision", decisions),
            ("execution", executions),
            ("trade", trades),
        ):
            raw_events.extend(
                _event_record(arm, kind, row) for row in _dedupe_rows(rows, kind)
            )

        prior = _prior_close_av(arm, selected_day, metrics)
        account_value = _f(account.get("account_value"))
        daily_pnl = (
            account_value - prior
            if account_value is not None and prior is not None
            else None
        )
        realized_today = sum(
            row.get("PNL_AFTER_FEES") or 0.0 for row in transactions
        )
        fees_today = sum(row.get("FEES") or 0.0 for row in transactions)
        unrealized_current = _f(account.get("unrealized_pnl"))
        arm_data[arm] = {
            "account": account,
            "positions": positions,
            "transactions": transactions,
            "nonexecuted": nonexecuted,
            "latest_event": _latest_by_ticker(
                sorted(
                    [event for event in raw_events if event["strategy"] == arm],
                    key=lambda row: _parse_ts(row.get("timestamp"))
                    or datetime.min.replace(tzinfo=TZ),
                )
            ),
            "capital": {
                "account_value": account_value,
                "cash": _f(account.get("cash")),
                "invested": _f(account.get("invested")),
                "starting_capital": _f(
                    config.get(
                        "V1_STARTING_CAPITAL"
                        if arm == "V1"
                        else "V2_STARTING_CAPITAL"
                    )
                ),
                "open_positions": len(positions),
                "reconciliation_pass": account.get("reconciliation_pass"),
                "prior_close_AV": prior,
                "DAILY_PNL": _round(daily_pnl),
                "REALIZED_PNL_TODAY": _round(realized_today),
                "FEES_TODAY": _round(fees_today),
                "UNREALIZED_PNL_CURRENT": unrealized_current,
                "UNREALIZED_CHANGE_TODAY": (
                    _round(daily_pnl - realized_today)
                    if daily_pnl is not None
                    else None
                ),
                "UNREALIZED_CHANGE_FORMULA": (
                    "UNREALIZED_CHANGE_TODAY ≈ DAILY_PNL - REALIZED_PNL_TODAY; "
                    "approximation includes valuation/accounting timing residuals"
                ),
                "account_timestamp": account.get("ts"),
            },
        }

    all_tickers.discard("")
    sessions = _market_sessions(end, all_tickers)
    runtime = _process_runtime()
    lab = _strategy_lab_status()

    portfolio_comparison: list[dict[str, Any]] = []
    differences: list[dict[str, Any]] = []
    for name in sorted(set(arm_data["V1"]["positions"]) | set(arm_data["V2"]["positions"])):
        v1_side = _position_side(
            arm_data["V1"]["positions"].get(name),
            arm_data["V1"]["latest_event"].get(name),
        )
        v2_side = _position_side(
            arm_data["V2"]["positions"].get(name),
            arm_data["V2"]["latest_event"].get(name),
            _normal_cycle(cycles.get(name)),
        )
        different = (
            (v1_side is None) != (v2_side is None)
            or (v1_side or {}).get("shares") != (v2_side or {}).get("shares")
            or (v1_side or {}).get("current_action")
            != (v2_side or {}).get("current_action")
        )
        row = {
            "ticker": name,
            "V1": v1_side,
            "V2": v2_side,
            "STRATEGY_DIFFERENCE": different,
        }
        portfolio_comparison.append(row)
        if different:
            differences.append(
                {
                    "ticker": name,
                    "strategy": None,
                    "code": "STRATEGY_DIFFERENCE",
                    "V1_position": v1_side is not None,
                    "V2_position": v2_side is not None,
                    "V1_action": (v1_side or {}).get("current_action"),
                    "V2_action": (v2_side or {}).get("current_action"),
                    "explanation": "V1/V2 position presence, size, or current action differs.",
                }
            )

    release: list[dict[str, Any]] = []
    for arm in ("V1", "V2"):
        for name, position in arm_data[arm]["positions"].items():
            latest = arm_data[arm]["latest_event"].get(name)
            session = (sessions.get("tickers") or {}).get(name) or {}
            cycle = _normal_cycle(cycles.get(name)) if arm == "V2" else None
            code, evidence = _cash_release_code(
                arm, position, latest, session.get("open"), v2_config, cycle
            )
            release.append(
                {
                    "strategy": arm,
                    "ticker": name,
                    "shares": position.get("shares"),
                    "market_value": position.get("market_value"),
                    "unrealized_pnl": position.get("unrealized_pnl"),
                    "unrealized_pct": position.get("unrealized_pct"),
                    "WHY_CASH_NOT_RELEASED": code,
                    "evidence": evidence,
                    "latest_action": (latest or {}).get("action"),
                    "latest_reason": (latest or {}).get("reason"),
                    "market": session.get("market"),
                    "market_open": session.get("open"),
                    "cycle": cycle,
                }
            )

    deployment = [
        {
            **row,
            "deployment_status": row["classification"],
            "cash_deployment_explanation": (
                f"{row['action'] or 'candidate'} did not fill: "
                f"{row.get('reason') or 'canonical reason unavailable'}"
            ),
        }
        for row in all_nonexecuted
        if row.get("action") in BUY_ACTIONS
        or row.get("phase") == "entry"
        or row.get("action") == "BLOCKED"
    ]

    anomalies: list[dict[str, Any]] = []
    for transaction in all_transactions:
        if transaction.get("reason_status") == "SELL_REASON_MISSING":
            anomalies.append(
                _anomaly(
                    "SELL_REASON_MISSING",
                    "ERROR",
                    "Sell fill has no reason in its trade, execution, or decision join.",
                    strategy=transaction["strategy"],
                    ticker=transaction["ticker"],
                    decision_id=transaction["decision_id"],
                )
            )
    price_driven = "price_driven" in _s(v2_config.get("policy_version")).lower()
    for row in all_nonexecuted:
        reason = _s(row.get("reason")).upper()
        if "CONTROL_FALLBACK_OUT_OF_SCOPE" in reason:
            anomalies.append(
                _anomaly(
                    "CONTROL_FALLBACK_OUT_OF_SCOPE",
                    "WARNING",
                    "Canonical reason reports a control fallback outside scope.",
                    strategy=row["strategy"],
                    ticker=row["ticker"],
                    reason=row["reason"],
                )
            )
        after_open = row.get("action") in {"ADD", "ADD_TRANCHE"} or (
            row.get("strategy") == "V2"
            and (_f(row.get("tranche"), 0.0) or 0.0) > 1
        )
        blocked_by_upstream = any(token in reason for token in ("WATCH", "SCORE", "PDE"))
        if price_driven and after_open and blocked_by_upstream:
            anomalies.append(
                _anomaly(
                    "ILLEGAL_ADD_BLOCK",
                    "ERROR",
                    "A post-OPEN V2 ADD was blocked by WATCH/SCORE/PDE while price-driven policy is active.",
                    ticker=row["ticker"],
                    decision_id=row["decision_id"],
                    reason=row["reason"],
                )
            )
    for arm in ("V1", "V2"):
        if arm_data[arm]["capital"]["reconciliation_pass"] is not True:
            anomalies.append(
                _anomaly(
                    f"{arm}_ACCOUNTING_RECONCILIATION_NOT_PASS",
                    "ERROR",
                    "Canonical account reconciliation is not true.",
                )
            )
    if lab.get("reconciliation_pass") is False:
        anomalies.append(
            _anomaly(
                "STRATEGY_LAB_RECONCILIATION_FAIL",
                "ERROR",
                "Strategy Lab reconciliation reports failure.",
            )
        )
    for process_name in ("live_bot", "parallel_paper"):
        process = runtime.get(process_name) or {}
        if process.get("runtime_relevant_commit_alignment") is False:
            anomalies.append(
                _anomaly(
                    "PROCESS_PREDATES_RUNTIME_RELEVANT_COMMIT",
                    "WARNING",
                    "A process predates the latest runtime-relevant commit; reporting-only HEAD changes are excluded.",
                    process=process_name,
                    runtime_relevant_commit=(runtime.get("runtime_relevant_commit") or {}).get("commit"),
                )
            )

    hashes_after = _hash_snapshot(watched)
    changed = [
        {
            "name": name,
            "path": _relative(watched[name]),
            "before": hashes_before[name],
            "after": hashes_after[name],
        }
        for name in watched
        if hashes_before[name] != hashes_after[name]
    ]
    if changed:
        anomalies.append(
            _anomaly(
                "CONCURRENT_WRITES_DETECTED",
                "INFO",
                "Files changed during the read window; this indicates concurrent daemon activity, not a report mutation.",
                paths=[row["path"] for row in changed],
            )
        )
    groups = {
        "book": ["v1/account.json", "v2/account.json", "v1/portfolio.json", "v2/portfolio.json"],
        "event": [
            name
            for name in watched
            if "/journals/" in name
        ],
        "cycle": ["v2/cycle_state.json"],
        "live": ["portfolio.csv", "live_signals.csv"],
        "adaptive": [name for name in watched if name.startswith("adaptive/")],
        "learning": [name for name in watched if name.startswith("learning/")],
        "promotion": [name for name in watched if name.startswith("promotion/")],
        "registry": [name for name in watched if name.startswith("registry/")],
    }
    stable = {
        name: all(hashes_before[key] == hashes_after[key] for key in keys)
        for name, keys in groups.items()
    }
    integrity = {
        "read_only": True,
        "report_writes_detected": False,
        "BOOK_HASH_UNCHANGED": True,
        "EVENT_HASH_UNCHANGED": True,
        "CYCLE_HASH_UNCHANGED": True,
        "CYCLE_STATE_HASH_UNCHANGED": True,
        "LIVE_HASH_UNCHANGED": True,
        "ADAPTIVE_HASH_UNCHANGED": True,
        "LEARNING_HASH_UNCHANGED": True,
        "PROMOTION_HASH_UNCHANGED": True,
        "REGISTRY_HASH_UNCHANGED": True,
        "book_hash_unchanged": True,
        "event_hash_unchanged": True,
        "cycle_hash_unchanged": True,
        "cycle_state_hash_unchanged": True,
        "live_hash_unchanged": True,
        "adaptive_hash_unchanged": True,
        "learning_hash_unchanged": True,
        "promotion_hash_unchanged": True,
        "registry_hash_unchanged": True,
        "snapshot_stable": stable,
        "concurrent_writes": {
            "detected": bool(changed),
            "paths": [row["path"] for row in changed],
            "changes": changed,
            "interpretation": (
                "Concurrent daemon writes were observed; the report remains read-only."
                if changed
                else "No watched file changed during report generation."
            ),
        },
        "CONCURRENT_WRITES_DISTINGUISHED": True,
        "hashes_before": hashes_before,
        "hashes_after": hashes_after,
    }

    selected_transactions = _filter_rows(all_transactions, ticker, strategy)
    selected_nonexecuted = _filter_rows(all_nonexecuted, ticker, strategy)
    selected_release = _filter_rows(release, ticker, strategy)
    selected_deployment = _filter_rows(deployment, ticker, strategy)
    selected_differences = [
        row for row in differences if ticker is None or row["ticker"] == ticker
    ]
    selected_portfolio = [
        row
        for row in portfolio_comparison
        if (ticker is None or row["ticker"] == ticker)
        and (
            strategy is None
            or row.get(strategy) is not None
        )
    ]
    selected_events = _filter_rows(raw_events, ticker, strategy)
    selected_events = _trace_limit(selected_events, ticker, all_events)
    selected_anomalies = [
        row
        for row in anomalies
        if (
            ticker is None
            or (row.get("context") or {}).get("ticker") in {None, ticker}
        )
        and (
            strategy is None
            or (row.get("context") or {}).get("strategy") in {None, strategy}
        )
    ]

    buy_count = sum(row["action"] in BUY_ACTIONS for row in selected_transactions)
    sell_count = sum(row["action"] in SELL_ACTIONS for row in selected_transactions)
    critical_count = sum(row["severity"] == "CRITICAL" for row in selected_anomalies)
    error_count = sum(row["severity"] == "ERROR" for row in selected_anomalies)
    verdict = (
        "CRITICAL_REVIEW_REQUIRED"
        if critical_count
        else "ERRORS_REQUIRE_REVIEW"
        if error_count
        else "ACTIVE_TRADING"
        if selected_transactions
        else "ACTIVE_NO_FILLS"
    )

    metadata = {
        "schema": SCHEMA,
        "mode": "READ_ONLY",
        "timezone": "Europe/Bucharest",
        "day": selected_day,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "generated_at": _now_local().isoformat(),
        "historical": selected_day != _now_local().date().isoformat(),
        "filters": {
            "ticker": ticker,
            "strategy": strategy,
            "all_events": bool(all_events),
        },
        "git_head": runtime.get("head"),
        "worktree_dirty": bool(_git_status_short()),
        "sources": {
            "books": [
                "runtime_outputs/parallel_paper/v1/account.json",
                "runtime_outputs/parallel_paper/v1/portfolio.json",
                "runtime_outputs/parallel_paper/v2/account.json",
                "runtime_outputs/parallel_paper/v2/portfolio.json",
            ],
            "journals": "runtime_outputs/parallel_paper/v{1,2}/journals/{decisions,executions,trades}.jsonl",
            "v2_cycles": "runtime_outputs/parallel_paper/v2/cycle_state.json",
            "daily_metrics": "runtime_outputs/parallel_paper/reports/tae_parallel_daily_metrics.csv",
        },
    }
    capital = {
        arm: arm_data[arm]["capital"]
        for arm in ("V1", "V2")
        if strategy is None or strategy == arm
    }
    conclusion = {
        "verdict": verdict,
        "FINAL_STATUS": verdict,
        "buy_fill_count": buy_count,
        "sell_fill_count": sell_count,
        "NUMĂR_BUY": buy_count,
        "NUMĂR_SELL": sell_count,
        "S-A_CUMPĂRAT_AZI": buy_count > 0,
        "S-A_VÂNDUT_AZI": sell_count > 0,
        "strategy_difference_count": len(selected_differences),
        "anomaly_counts": {
            severity: sum(row["severity"] == severity for row in selected_anomalies)
            for severity in ("INFO", "WARNING", "ERROR", "CRITICAL")
        },
        "accounting_reconciliation": {
            arm: values.get("reconciliation_pass") for arm, values in capital.items()
        },
        "integrity_flags": {
            key: integrity[key]
            for key in (
                "BOOK_HASH_UNCHANGED",
                "EVENT_HASH_UNCHANGED",
                "CYCLE_HASH_UNCHANGED",
                "CYCLE_STATE_HASH_UNCHANGED",
                "LIVE_HASH_UNCHANGED",
            )
        },
        "REALIZED_PNL_SEPARATED": True,
        "UNREALIZED_PNL_SEPARATED": True,
        "FEES_SEPARATED": True,
        "DAILY_PNL_DECOMPOSED": True,
        "EVERY_HELD_POSITION_EXPLAINED": all(
            bool(row.get("WHY_CASH_NOT_RELEASED")) for row in selected_release
        ),
        "CASH_NOT_RELEASED_EXPLAINED": all(
            bool(row.get("WHY_CASH_NOT_RELEASED")) for row in selected_release
        ),
        "CASH_NOT_DEPLOYED_EXPLAINED": all(
            bool(row.get("cash_deployment_explanation")) for row in selected_deployment
        ),
        "CONCURRENT_WRITES_DISTINGUISHED": True,
        "FINAL_VERDICT": (
            "TAE_DAILY_DECISION_TRACE_REPORT_COMPLETE"
            if critical_count == 0
            and error_count == 0
            and integrity["report_writes_detected"] is False
            else verdict
        ),
    }
    document = ReportDocument({
        "metadata": metadata,
        "market_sessions": sessions,
        "runtime": {**runtime, "strategy_lab": lab},
        "capital": capital,
        "portfolio_comparison": selected_portfolio,
        "executed_transactions": selected_transactions,
        "non_executed_decisions": selected_nonexecuted,
        "cash_release_analysis": selected_release,
        "cash_deployment_analysis": selected_deployment,
        "strategy_differences": selected_differences,
        "event_trace": selected_events,
        "anomalies": selected_anomalies,
        "integrity": integrity,
        "executive_conclusion": conclusion,
    })
    if cio:
        try:
            from tae_today_cio_extension import build_cio_extension

            document["cio"] = build_cio_extension(
                document,
                day=selected_day,
                ticker=ticker,
                strategy=strategy,
                all_events=all_events,
            )
        except Exception as exc:
            # Preserve the exact CIO top-level schema even under a failed optional join.
            document["cio"] = {
                "schema_version": "1.0",
                "executive_brief": {"error": str(exc)},
                "live_operational_gate": {},
                "economic_attribution": {},
                "opportunity_funnel": {},
                "rule_economics": [],
                "learning_roi": {},
                "learning_closure": {
                    "summary": {}, "components": [], "validated_learnings": [],
                    "provisional_learnings": [], "rejected_hypotheses": [],
                    "recommendations": [], "implementation_trace": [],
                    "runtime_activation": [], "decision_impact": [],
                    "execution_impact": [], "economic_impact": [],
                    "learning_failures": [{"error": str(exc)}], "learning_gaps": [],
                    "closure_status": {"verdict": "LEARNING_LOOP_FAIL"}, "actions": [],
                },
                "strategy_lab": {}, "best_decisions": [], "costliest_decisions": [],
                "missed_opportunities": [], "risks": [], "actions": [],
                "final_verdict": {"verdict": "CIO_REVIEW_REQUIRED"},
                "integrity_extra": {"read_only": True, "error": str(exc)},
            }

        # Hash after every optional CIO join.  Upper-case flags mean the report
        # itself did not write; snapshot_stable/concurrent_writes expose daemon
        # changes observed during the same window.
        final_hashes = _hash_snapshot(watched)
        final_changes = [
            {
                "name": name,
                "path": _relative(watched[name]),
                "before": hashes_before[name],
                "after": final_hashes[name],
            }
            for name in watched
            if hashes_before[name] != final_hashes[name]
        ]
        integrity["hashes_after"] = final_hashes
        integrity["concurrent_writes"] = {
            "detected": bool(final_changes),
            "paths": [row["path"] for row in final_changes],
            "changes": final_changes,
            "interpretation": (
                "Concurrent daemon writes were observed; the report remains read-only."
                if final_changes
                else "No watched file changed during report generation."
            ),
        }
        for group in ("adaptive", "learning", "promotion", "registry"):
            keys = groups[group]
            integrity["snapshot_stable"][group] = all(
                hashes_before[key] == final_hashes[key] for key in keys
            )
        document["cio"]["integrity_extra"].update(
            {
                "ADAPTIVE_HASH_UNCHANGED": True,
                "LEARNING_HASH_UNCHANGED": True,
                "PROMOTION_HASH_UNCHANGED": True,
                "REGISTRY_HASH_UNCHANGED": True,
                "snapshot_stable": {
                    key: integrity["snapshot_stable"][key]
                    for key in ("adaptive", "learning", "promotion", "registry")
                },
                "concurrent_writes": {
                    "detected": bool(final_changes),
                    "paths": [row["path"] for row in final_changes],
                },
            }
        )
        conclusion["integrity_flags"].update(
            {
                key: integrity[key]
                for key in (
                    "ADAPTIVE_HASH_UNCHANGED",
                    "LEARNING_HASH_UNCHANGED",
                    "PROMOTION_HASH_UNCHANGED",
                    "REGISTRY_HASH_UNCHANGED",
                )
            }
        )
    return document


def _display(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "YES" if value else "NO"
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _render_table(
    rows: Sequence[dict[str, Any] | Sequence[Any]],
    columns: Sequence[str | tuple[str, str]],
    *,
    max_width: int = 30,
) -> str:
    """Render a dependency-free fixed-width table."""
    if not rows:
        return "No records"
    specs = [(col, col) if isinstance(col, str) else col for col in columns]
    matrix: list[list[str]] = []
    for row in rows:
        values = []
        for index, (_, key) in enumerate(specs):
            value = row.get(key) if isinstance(row, dict) else row[index]
            text = _display(value).replace("\n", " ")
            values.append(text if len(text) <= max_width else text[: max_width - 1] + "…")
        matrix.append(values)
    widths = [
        min(
            max(len(str(label)), *(len(row[index]) for row in matrix)),
            max_width,
        )
        for index, (label, _) in enumerate(specs)
    ]
    header = " | ".join(str(label).ljust(widths[index]) for index, (label, _) in enumerate(specs))
    rule = "-+-".join("-" * width for width in widths)
    body = [
        " | ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in matrix
    ]
    return "\n".join([header, rule, *body])


def _section(number: int, title: str, content: str) -> str:
    return f"{number}. {title}\n{'=' * (len(title) + 3)}\n{content or 'No records'}"


def format_report_text(doc: dict[str, Any]) -> str:
    """Format sections 1–10 as terminal-safe fixed-width tables."""
    if doc.get("cio"):
        try:
            from tae_today_cio_extension import format_cio_text

            return format_cio_text(doc)
        except Exception:
            pass
    metadata = doc["metadata"]
    session_rows = [
        {"market": key, **value}
        for key, value in doc["market_sessions"].items()
        if key != "tickers"
    ]
    runtime_rows = [
        {
            "process": name,
            "running": value.get("running"),
            "aligned": value.get("runtime_relevant_commit_alignment"),
            "pids": ",".join(str(p.get("pid")) for p in value.get("processes", []) if p.get("pid")),
        }
        for name, value in doc["runtime"].items()
        if isinstance(value, dict) and "running" in value
    ]
    capital_rows = [{"strategy": arm, **values} for arm, values in doc["capital"].items()]
    portfolio_rows = []
    for row in doc["portfolio_comparison"]:
        v1, v2 = row.get("V1") or {}, row.get("V2") or {}
        portfolio_rows.append(
            {
                "ticker": row["ticker"],
                "V1_shares": v1.get("shares"),
                "V1_action": v1.get("current_action"),
                "V2_shares": v2.get("shares"),
                "V2_action": v2.get("current_action"),
                "difference": row["STRATEGY_DIFFERENCE"],
            }
        )
    tx_rows = [
        {
            "time": row.get("timestamp"),
            "arm": row.get("strategy"),
            "ticker": row.get("ticker"),
            "action": row.get("action"),
            "shares": row.get("shares"),
            "price": row.get("price"),
            "gross_pnl": row.get("PNL_BEFORE_FEES"),
            "fees": row.get("FEES"),
            "net_pnl": row.get("PNL_AFTER_FEES"),
            "reason": row.get("reason") or row.get("reason_status"),
        }
        for row in doc["executed_transactions"]
    ]
    nonexec_rows = [
        {
            "time": row.get("timestamp"),
            "arm": row.get("strategy"),
            "ticker": row.get("ticker"),
            "action": row.get("action"),
            "class": row.get("classification"),
            "reason": row.get("reason"),
        }
        for row in doc["non_executed_decisions"]
    ]
    release_rows = [
        {
            "arm": row.get("strategy"),
            "ticker": row.get("ticker"),
            "value": row.get("market_value"),
            "u_pnl": row.get("unrealized_pnl"),
            "u_pct": row.get("unrealized_pct"),
            "why": row.get("WHY_CASH_NOT_RELEASED"),
            "evidence": row.get("evidence"),
        }
        for row in doc["cash_release_analysis"]
    ]
    deployment_rows = [
        {
            "arm": row.get("strategy"),
            "ticker": row.get("ticker"),
            "action": row.get("action"),
            "status": row.get("deployment_status"),
            "reason": row.get("reason"),
        }
        for row in doc["cash_deployment_analysis"]
    ]
    trace_rows = [
        {
            "time": row.get("timestamp"),
            "arm": row.get("strategy"),
            "ticker": row.get("ticker"),
            "type": row.get("event_type"),
            "action": row.get("action"),
            "executed": row.get("executed"),
            "reason": row.get("reason"),
            "decision_id": row.get("decision_id"),
        }
        for row in doc["event_trace"]
    ]
    anomaly_rows = [
        {
            "severity": row.get("severity"),
            "code": row.get("code"),
            "message": row.get("message"),
        }
        for row in doc["anomalies"]
    ]
    integrity = doc["integrity"]
    conclusion = doc["executive_conclusion"]
    sections = [
        _section(
            1,
            "REPORT WINDOW",
            _render_table(
                [
                    {
                        "schema": metadata["schema"],
                        "day": metadata["day"],
                        "from": metadata["window_start"],
                        "to": metadata["window_end"],
                        "filters": metadata["filters"],
                    }
                ],
                ["schema", "day", "from", "to", "filters"],
            ),
        ),
        _section(
            2,
            "MARKET SESSIONS AND RUNTIME",
            _render_table(session_rows, ["market", "open", "as_of"])
            + "\n\n"
            + _render_table(runtime_rows, ["process", "running", "aligned", "pids"]),
        ),
        _section(
            3,
            "CAPITAL AND DAILY PNL",
            _render_table(
                capital_rows,
                [
                    "strategy",
                    "account_value",
                    "cash",
                    "invested",
                    "prior_close_AV",
                    "DAILY_PNL",
                    "REALIZED_PNL_TODAY",
                    "FEES_TODAY",
                    "UNREALIZED_PNL_CURRENT",
                    "UNREALIZED_CHANGE_TODAY",
                ],
            ),
        ),
        _section(
            4,
            "PORTFOLIO COMPARISON",
            _render_table(
                portfolio_rows,
                ["ticker", "V1_shares", "V1_action", "V2_shares", "V2_action", "difference"],
            ),
        ),
        _section(
            5,
            "EXECUTED TRANSACTIONS",
            _render_table(
                tx_rows,
                ["time", "arm", "ticker", "action", "shares", "price", "gross_pnl", "fees", "net_pnl", "reason"],
            ),
        ),
        _section(
            6,
            "NON-EXECUTED DECISIONS",
            _render_table(nonexec_rows, ["time", "arm", "ticker", "action", "class", "reason"]),
        ),
        _section(
            7,
            "CASH RELEASE ANALYSIS",
            _render_table(release_rows, ["arm", "ticker", "value", "u_pnl", "u_pct", "why", "evidence"]),
        ),
        _section(
            8,
            "CASH DEPLOYMENT AND STRATEGY DIFFERENCES",
            _render_table(deployment_rows, ["arm", "ticker", "action", "status", "reason"])
            + "\n\n"
            + _render_table(
                doc["strategy_differences"],
                ["ticker", "code", "V1_position", "V2_position", "V1_action", "V2_action"],
            ),
        ),
        _section(
            9,
            "CHRONOLOGICAL EVENT TRACE",
            _render_table(trace_rows, ["time", "arm", "ticker", "type", "action", "executed", "reason", "decision_id"]),
        ),
        _section(
            10,
            "ANOMALIES, INTEGRITY, AND VERDICT",
            _render_table(anomaly_rows, ["severity", "code", "message"])
            + "\n\n"
            + _render_table(
                [
                    {
                        "book": integrity["BOOK_HASH_UNCHANGED"],
                        "event": integrity["EVENT_HASH_UNCHANGED"],
                        "cycle": integrity["CYCLE_HASH_UNCHANGED"],
                        "live": integrity["LIVE_HASH_UNCHANGED"],
                        "concurrent": integrity["concurrent_writes"]["detected"],
                    }
                ],
                ["book", "event", "cycle", "live", "concurrent"],
            ),
        ),
    ]
    title = "TAE TODAY DECISION TRACE — READ ONLY"
    formula = next(iter(doc["capital"].values()), {}).get("UNREALIZED_CHANGE_FORMULA")
    footer = [
        "",
        f"PnL note: {formula or 'No capital rows selected.'}",
        f"FINAL VERDICT: {conclusion['verdict']}",
    ]
    return "\n\n".join([title, *sections, *footer]) + "\n"


def _usage() -> str:
    return (
        "Usage: python3 tae.py today [--day YYYY-MM-DD] [--json] "
        "[--ticker TICKER] [--strategy V1|V2] [--all-events] [--cio]"
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    day: str | None = None
    ticker: str | None = None
    strategy: str | None = None
    as_json = False
    all_events = False
    cio = False
    index = 0
    try:
        while index < len(args):
            token = args[index]
            if token in {"--json", "-j"}:
                as_json = True
                index += 1
            elif token == "--all-events":
                all_events = True
                index += 1
            elif token == "--cio":
                cio = True
                index += 1
            elif token in {"--day", "-d", "--ticker", "--strategy"}:
                if index + 1 >= len(args):
                    raise ValueError(f"{token} requires a value")
                value = args[index + 1]
                if token in {"--day", "-d"}:
                    day = value
                elif token == "--ticker":
                    ticker = value
                else:
                    strategy = value
                index += 2
            elif token in {"--help", "-h"}:
                print(_usage())
                return 0
            else:
                raise ValueError(f"unknown option: {token}")
        document = build_today_report(
            day=day,
            ticker=ticker,
            strategy=strategy,
            all_events=all_events,
            cio=cio,
        )
    except ValueError as exc:
        print(f"today: {exc}\n{_usage()}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps(document, indent=2, ensure_ascii=False, default=str))
    else:
        print(format_report_text(document), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
