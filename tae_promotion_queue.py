#!/usr/bin/env python3
"""
TAE Sprint X.10E — Governed Promotion Queue

GOVERNANCE / CONFIG WORKFLOW ONLY | NO_BROKER | NO_EXECUTION | NO_STRATEGY_CHANGE
Does NOT modify live_bot.py or trading logic.
Only `promote-approved` writes watchlist.txt (with backup).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SAFETY_BANNER = (
    "GOVERNED_CONFIG_CHANGE | NO_BROKER | NO_EXECUTION | NO_STRATEGY_CHANGE | "
    "OPERATOR_APPROVAL_REQUIRED"
)

DEFAULT_ROOT = Path(".")
WATCHLIST_FILE = "watchlist.txt"
PORTFOLIO_FILE = "portfolio.csv"
CANDIDATE_QUEUE_FILE = "tae_candidate_queue.json"
PROPOSAL_FILE = "tae_watchlist_proposal.json"
QUEUE_JSON = "tae_promotion_queue.json"
QUEUE_MD = "tae_promotion_queue.md"
QUEUE_CSV = "tae_promotion_queue.csv"
BACKUP_DIR = "backups"

MAX_PROMOTIONS_PER_RUN = 10
DEFAULT_EXPIRE_HOURS = 24.0

STATES = ("PROPOSED", "APPROVED", "PROMOTED", "REJECTED", "ROLLED_BACK", "EXPIRED")
ACTIVE_BUILD_STATES = {"PROPOSED", "APPROVED"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _read_watchlist(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [
        line.strip().upper()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _read_open_positions(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    holdings: dict[str, float] = {}
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            for row in csv.DictReader(handle):
                ticker = str(row.get("Ticker") or "").strip().upper()
                if not ticker:
                    continue
                action = str(row.get("Action") or "").strip().upper()
                shares = float(row.get("Shares") or 0)
                if action == "BUY":
                    holdings[ticker] = holdings.get(ticker, 0.0) + shares
                elif action == "SELL":
                    holdings[ticker] = holdings.get(ticker, 0.0) - shares
    except (OSError, ValueError):
        return set()
    return {t for t, s in holdings.items() if s > 1e-6}


def _empty_queue(expire_hours: float) -> dict[str, Any]:
    return {
        "schema": "tae.promotion_queue.v1",
        "mode": "GOVERNED_CONFIG_WORKFLOW",
        "live_trading_impact": "NONE",
        "generated_at": _utc_now_iso(),
        "safety_mode": SAFETY_BANNER,
        "expires_after_hours": expire_hours,
        "queue_status": "EMPTY",
        "next_operator_action": "Run build after scanner refresh produces promotion-eligible candidates.",
        "summary": {
            "proposed": 0,
            "approved": 0,
            "promoted": 0,
            "rejected": 0,
            "rolled_back": 0,
            "expired": 0,
            "total_items": 0,
        },
        "items": [],
        "action_history": [],
        "last_promotion": None,
        "sources": {
            "candidate_queue": CANDIDATE_QUEUE_FILE,
            "watchlist_proposal": PROPOSAL_FILE,
            "watchlist": WATCHLIST_FILE,
            "portfolio": PORTFOLIO_FILE,
        },
    }


def _load_queue(root: Path) -> dict[str, Any]:
    payload = _load_json(root / QUEUE_JSON)
    if payload and payload.get("schema") == "tae.promotion_queue.v1":
        return payload
    return _empty_queue(DEFAULT_EXPIRE_HOURS)


def _save_queue(root: Path, queue: dict[str, Any]) -> None:
    queue["generated_at"] = _utc_now_iso()
    queue["summary"] = _compute_summary(queue.get("items") or [])
    (root / QUEUE_JSON).write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (root / QUEUE_MD).write_text(_render_markdown(queue), encoding="utf-8")
    _write_csv(queue, root / QUEUE_CSV)


def _compute_summary(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {state.lower(): 0 for state in STATES}
    for item in items:
        state = str(item.get("state", "")).upper()
        key = state.lower()
        if key in counts:
            counts[key] += 1
    return {
        "proposed": counts["proposed"],
        "approved": counts["approved"],
        "promoted": counts["promoted"],
        "rejected": counts["rejected"],
        "rolled_back": counts["rolled_back"],
        "expired": counts["expired"],
        "total_items": len(items),
    }


def _append_history(
    queue: dict[str, Any],
    action: str,
    *,
    ticker: str | None = None,
    detail: str = "",
    operator: str | None = None,
) -> None:
    queue.setdefault("action_history", []).append(
        {
            "timestamp": _utc_now_iso(),
            "action": action,
            "ticker": ticker,
            "operator": operator or os.getenv("USER", "operator"),
            "detail": detail,
        }
    )


def _expire_stale_items(queue: dict[str, Any], expire_hours: float) -> int:
    cutoff = _utc_now() - timedelta(hours=expire_hours)
    expired_count = 0
    for item in queue.get("items") or []:
        state = str(item.get("state", "")).upper()
        if state not in {"PROPOSED", "APPROVED"}:
            continue
        ref = item.get("approved_at") or item.get("proposed_at")
        dt = _parse_iso(ref)
        if dt and dt < cutoff:
            item["state"] = "EXPIRED"
            item["expired_at"] = _utc_now_iso()
            expired_count += 1
    return expired_count


def _eligible_candidates(root: Path) -> tuple[list[dict[str, Any]], str, str]:
    """Return (eligible_items, queue_status_hint, next_action_hint)."""
    cq = _load_json(root / CANDIDATE_QUEUE_FILE) or {}
    proposal = _load_json(root / PROPOSAL_FILE) or {}
    watchlist = set(_read_watchlist(root / WATCHLIST_FILE))
    held = _read_open_positions(root / PORTFOLIO_FILE)

    cq_summary = cq.get("summary") or {}
    recommended_action = str(cq_summary.get("recommended_action") or "")

    eligible: list[dict[str, Any]] = []
    seen: set[str] = set()

    pq = cq.get("promotion_queue") or {}
    for item in pq.get("top_10_promotion_eligible") or []:
        ticker = str(item.get("ticker") or "").upper().strip()
        if not ticker or ticker in seen:
            continue
        if str(item.get("classification", "")).upper() != "PROMOTION_ELIGIBLE":
            continue
        if ticker in watchlist or ticker in held:
            continue
        seen.add(ticker)
        eligible.append(dict(item))

    for item in proposal.get("recommended_additions_max_10") or []:
        ticker = str(item.get("ticker") or "").upper().strip()
        if not ticker or ticker in seen:
            continue
        if ticker in watchlist or ticker in held:
            continue
        seen.add(ticker)
        eligible.append(
            {
                "ticker": ticker,
                "market": item.get("market"),
                "rank_score": item.get("rank_score"),
                "source": item.get("primary_source") or item.get("source"),
                "signal": item.get("signal"),
                "classification": "PROMOTION_ELIGIBLE",
            }
        )

    if eligible:
        return eligible[:MAX_PROMOTIONS_PER_RUN], "READY_FOR_OPERATOR", (
            "Review proposed tickers: approve with `approve TICKER`, then `promote-approved`."
        )

    if recommended_action == "WAIT_FOR_MARKET_OPEN":
        return [], "WAIT_FOR_MARKET_OPEN", (
            "No promotion-eligible candidates — US/other sessions closed. "
            "Re-run `build` after market open."
        )
    if recommended_action == "REFRESH_SCANNER":
        return [], "REFRESH_SCANNER", "Run scanner refresh before building promotion queue."
    return [], "NO_ELIGIBLE_CANDIDATES", (
        "No promotion-eligible candidates in candidate queue / proposal."
    )


def cmd_build(root: Path, *, expire_hours: float = DEFAULT_EXPIRE_HOURS) -> dict[str, Any]:
    queue = _load_queue(root)
    queue["expires_after_hours"] = expire_hours
    expired = _expire_stale_items(queue, expire_hours)

    existing_by_ticker = {
        str(i.get("ticker", "")).upper(): i for i in queue.get("items") or [] if i.get("ticker")
    }
    eligible, status_hint, next_action = _eligible_candidates(root)

    added = 0
    for cand in eligible:
        ticker = str(cand.get("ticker")).upper()
        prev = existing_by_ticker.get(ticker)
        if prev and str(prev.get("state", "")).upper() in {
            "APPROVED",
            "PROMOTED",
            "REJECTED",
            "ROLLED_BACK",
        }:
            continue
        if prev and str(prev.get("state", "")).upper() in ACTIVE_BUILD_STATES:
            continue
        item = {
            "ticker": ticker,
            "market": cand.get("market"),
            "rank_score": cand.get("rank_score"),
            "source": cand.get("source") or cand.get("primary_source"),
            "signal": cand.get("signal"),
            "classification": cand.get("classification", "PROMOTION_ELIGIBLE"),
            "state": "PROPOSED",
            "proposed_at": _utc_now_iso(),
            "approved_at": None,
            "promoted_at": None,
            "rejected_at": None,
            "expired_at": None,
            "reject_reason": None,
        }
        queue.setdefault("items", []).append(item)
        existing_by_ticker[ticker] = item
        added += 1

    summary = _compute_summary(queue.get("items") or [])
    if summary["proposed"] or summary["approved"]:
        queue["queue_status"] = "READY_FOR_OPERATOR"
        queue["next_operator_action"] = (
            "Approve tickers with `approve TICKER`, then run `promote-approved`."
        )
    else:
        queue["queue_status"] = status_hint
        queue["next_operator_action"] = next_action

    _append_history(
        queue,
        "BUILD",
        detail=f"added={added} expired={expired} status={queue['queue_status']}",
    )
    _save_queue(root, queue)
    return queue


def _find_item(queue: dict[str, Any], ticker: str) -> dict[str, Any] | None:
    ticker = ticker.upper()
    for item in reversed(queue.get("items") or []):
        if str(item.get("ticker", "")).upper() == ticker:
            return item
    return None


def cmd_approve(root: Path, ticker: str) -> dict[str, Any]:
    queue = _load_queue(root)
    item = _find_item(queue, ticker)
    if not item:
        raise SystemExit(f"Ticker not in queue: {ticker}")
    state = str(item.get("state", "")).upper()
    if state != "PROPOSED":
        raise SystemExit(f"Cannot approve {ticker}: state is {state}, expected PROPOSED")
    item["state"] = "APPROVED"
    item["approved_at"] = _utc_now_iso()
    queue["queue_status"] = "APPROVED_PENDING_PROMOTE"
    queue["next_operator_action"] = "Run `promote-approved` to append approved tickers to watchlist.txt."
    _append_history(queue, "APPROVE", ticker=ticker.upper())
    _save_queue(root, queue)
    return queue


def cmd_reject(root: Path, ticker: str, reason: str) -> dict[str, Any]:
    queue = _load_queue(root)
    item = _find_item(queue, ticker)
    if not item:
        raise SystemExit(f"Ticker not in queue: {ticker}")
    state = str(item.get("state", "")).upper()
    if state not in {"PROPOSED", "APPROVED"}:
        raise SystemExit(f"Cannot reject {ticker}: state is {state}")
    item["state"] = "REJECTED"
    item["rejected_at"] = _utc_now_iso()
    item["reject_reason"] = reason or "Rejected by operator"
    _append_history(queue, "REJECT", ticker=ticker.upper(), detail=reason)
    summary = _compute_summary(queue.get("items") or [])
    if summary["approved"]:
        queue["queue_status"] = "APPROVED_PENDING_PROMOTE"
        queue["next_operator_action"] = "Run `promote-approved` for remaining approved tickers."
    elif summary["proposed"]:
        queue["queue_status"] = "READY_FOR_OPERATOR"
        queue["next_operator_action"] = "Review remaining proposed tickers."
    else:
        queue["queue_status"] = "NO_PENDING_ITEMS"
        queue["next_operator_action"] = "Run `build` when new promotion-eligible candidates appear."
    _save_queue(root, queue)
    return queue


def cmd_promote_approved(root: Path) -> dict[str, Any]:
    queue = _load_queue(root)
    watchlist_path = root / WATCHLIST_FILE
    existing = _read_watchlist(watchlist_path)
    existing_set = set(existing)

    approved = [
        item
        for item in queue.get("items") or []
        if str(item.get("state", "")).upper() == "APPROVED"
    ]
    if not approved:
        raise SystemExit("No APPROVED items to promote.")

    to_promote: list[dict[str, Any]] = []
    for item in approved:
        ticker = str(item.get("ticker", "")).upper()
        if ticker in existing_set or ticker in {i["ticker"] for i in to_promote}:
            item["state"] = "REJECTED"
            item["rejected_at"] = _utc_now_iso()
            item["reject_reason"] = "Duplicate at promote time"
            continue
        to_promote.append({"ticker": ticker, "item": item})
        if len(to_promote) >= MAX_PROMOTIONS_PER_RUN:
            break

    if not to_promote:
        raise SystemExit("All approved tickers were duplicates — nothing to promote.")

    stamp = _utc_now().strftime("%Y%m%d_%H%M%S")
    backup_path = root / BACKUP_DIR / f"watchlist_{stamp}.txt"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    if watchlist_path.is_file():
        backup_path.write_text(
            watchlist_path.read_text(encoding="utf-8", errors="replace"),
            encoding="utf-8",
        )
    else:
        backup_path.write_text("", encoding="utf-8")

    new_tickers = [t["ticker"] for t in to_promote]
    new_watchlist = existing + new_tickers
    watchlist_path.write_text("\n".join(new_watchlist) + "\n", encoding="utf-8")

    after = _read_watchlist(watchlist_path)
    if after != new_watchlist:
        watchlist_path.write_text(
            backup_path.read_text(encoding="utf-8", errors="replace"),
            encoding="utf-8",
        )
        raise RuntimeError("Watchlist verification failed — restored backup")

    promoted_at = _utc_now_iso()
    for entry in to_promote:
        item = entry["item"]
        item["state"] = "PROMOTED"
        item["promoted_at"] = promoted_at

    queue["last_promotion"] = {
        "applied_at": promoted_at,
        "backup_path": str(backup_path),
        "tickers": new_tickers,
        "old_count": len(existing),
        "new_count": len(new_watchlist),
        "rollback_command": f"cp {backup_path} {watchlist_path}",
    }
    queue["queue_status"] = "PROMOTED"
    queue["next_operator_action"] = (
        "Promotion applied. Optional rollback: `rollback-last`. Re-run scanner refresh on next cycle."
    )
    _append_history(
        queue,
        "PROMOTE_APPROVED",
        detail=f"promoted={','.join(new_tickers)} backup={backup_path}",
    )
    _save_queue(root, queue)
    return queue


def cmd_rollback_last(root: Path) -> dict[str, Any]:
    queue = _load_queue(root)
    last = queue.get("last_promotion")
    if not last or not last.get("backup_path"):
        raise SystemExit("No last promotion to rollback.")

    backup_path = Path(last["backup_path"])
    watchlist_path = root / WATCHLIST_FILE
    if not backup_path.is_file():
        raise SystemExit(f"Backup missing: {backup_path}")

    watchlist_path.write_text(
        backup_path.read_text(encoding="utf-8", errors="replace"),
        encoding="utf-8",
    )

    rolled_tickers = set(str(t).upper() for t in last.get("tickers") or [])
    for item in queue.get("items") or []:
        if str(item.get("ticker", "")).upper() in rolled_tickers and str(
            item.get("state", "")
        ).upper() == "PROMOTED":
            item["state"] = "ROLLED_BACK"
            item["rolled_back_at"] = _utc_now_iso()

    queue["queue_status"] = "ROLLED_BACK"
    queue["next_operator_action"] = "Rollback complete. Re-run `build` if needed."
    _append_history(
        queue,
        "ROLLBACK_LAST",
        detail=f"restored_from={backup_path} tickers={','.join(sorted(rolled_tickers))}",
    )
    queue["last_promotion"] = None
    _save_queue(root, queue)
    return queue


def cmd_status(root: Path) -> dict[str, Any]:
    queue = _load_queue(root)
    _expire_stale_items(queue, float(queue.get("expires_after_hours") or DEFAULT_EXPIRE_HOURS))
    _save_queue(root, queue)
    return queue


def _render_markdown(queue: dict[str, Any]) -> str:
    summary = queue.get("summary") or {}
    lines = [
        "# TAE Governed Promotion Queue",
        "",
        f"**Generated:** {queue.get('generated_at')}",
        f"**Queue status:** {queue.get('queue_status')}",
        f"**Next operator action:** {queue.get('next_operator_action')}",
        "",
        "## Summary",
        "",
        f"- Proposed: **{summary.get('proposed', 0)}**",
        f"- Approved: **{summary.get('approved', 0)}**",
        f"- Promoted: **{summary.get('promoted', 0)}**",
        f"- Rejected: **{summary.get('rejected', 0)}**",
        f"- Rolled back: **{summary.get('rolled_back', 0)}**",
        f"- Expired: **{summary.get('expired', 0)}**",
        "",
        "## Active items",
        "",
    ]
    active = [
        i
        for i in queue.get("items") or []
        if str(i.get("state", "")).upper() in {"PROPOSED", "APPROVED"}
    ]
    if active:
        for item in active[:15]:
            lines.append(
                f"- **{item.get('ticker')}** [{item.get('state')}] "
                f"rank={item.get('rank_score')} market={item.get('market')}"
            )
    else:
        lines.append("- *(none)*")

    last = queue.get("last_promotion")
    if last:
        lines.extend(
            [
                "",
                "## Last promotion",
                "",
                f"- Applied: {last.get('applied_at')}",
                f"- Tickers: {', '.join(last.get('tickers') or [])}",
                f"- Backup: `{last.get('backup_path')}`",
                f"- Rollback: `{last.get('rollback_command')}`",
            ]
        )

    lines.extend(
        [
            "",
            "## Governance",
            "",
            "- `build` / `approve` / `reject` do **NOT** write watchlist.txt",
            "- Only `promote-approved` appends to watchlist (max 10, backup first)",
            "- `rollback-last` restores last backup",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_csv(queue: dict[str, Any], path: Path) -> None:
    fields = [
        "ticker",
        "market",
        "rank_score",
        "source",
        "signal",
        "state",
        "proposed_at",
        "approved_at",
        "promoted_at",
        "rejected_at",
        "expired_at",
        "reject_reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for item in queue.get("items") or []:
            writer.writerow(item)


def _print_status(queue: dict[str, Any]) -> None:
    summary = queue.get("summary") or {}
    print("===== TAE PROMOTION QUEUE =====")
    print(f"Status: {queue.get('queue_status')}")
    print(f"Next action: {queue.get('next_operator_action')}")
    print(
        f"Counts: proposed={summary.get('proposed')} approved={summary.get('approved')} "
        f"promoted={summary.get('promoted')} rejected={summary.get('rejected')} "
        f"expired={summary.get('expired')}"
    )
    proposed = [
        i for i in queue.get("items") or [] if str(i.get("state", "")).upper() == "PROPOSED"
    ]
    if proposed:
        print("Top proposed:")
        for item in proposed[:10]:
            print(
                f"  - {item.get('ticker')} ({item.get('market')}) "
                f"rank={item.get('rank_score')}"
            )
    else:
        print("Top proposed: (none)")
    print(f"Output: {QUEUE_JSON}, {QUEUE_MD}, {QUEUE_CSV}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TAE governed promotion queue")
    parser.add_argument("--root", default=".", help="Project root")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Build queue from promotion-eligible candidates")
    p_build.add_argument(
        "--expire-hours",
        type=float,
        default=DEFAULT_EXPIRE_HOURS,
        help="Expire PROPOSED/APPROVED older than N hours",
    )

    p_approve = sub.add_parser("approve", help="Approve a proposed ticker")
    p_approve.add_argument("ticker", help="Ticker symbol")

    p_reject = sub.add_parser("reject", help="Reject a proposed/approved ticker")
    p_reject.add_argument("ticker", help="Ticker symbol")
    p_reject.add_argument("--reason", default="Rejected by operator", help="Rejection reason")

    sub.add_parser("promote-approved", help="Promote all APPROVED tickers to watchlist.txt")
    sub.add_parser("status", help="Show queue status (expires stale items)")
    sub.add_parser("rollback-last", help="Rollback last promotion from backup")

    args = parser.parse_args(argv)
    root = Path(args.root)

    if args.command == "build":
        queue = cmd_build(root, expire_hours=args.expire_hours)
    elif args.command == "approve":
        queue = cmd_approve(root, args.ticker)
    elif args.command == "reject":
        queue = cmd_reject(root, args.ticker, args.reason)
    elif args.command == "promote-approved":
        queue = cmd_promote_approved(root)
    elif args.command == "rollback-last":
        queue = cmd_rollback_last(root)
    elif args.command == "status":
        queue = cmd_status(root)
    else:
        parser.error(f"Unknown command: {args.command}")
        return 1

    _print_status(queue)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
