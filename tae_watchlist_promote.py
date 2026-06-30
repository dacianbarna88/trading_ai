#!/usr/bin/env python3
"""
TAE Governed Watchlist Promotion

GOVERNED_CONFIG_CHANGE | NO_BROKER | NO_EXECUTION | NO_STRATEGY_CHANGE
Does NOT modify live_bot.py or trading logic.
Applies recommended additions from tae_watchlist_proposal.json to watchlist.txt with backup + rollback metadata.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAFETY_BANNER = (
    "GOVERNED_CONFIG_CHANGE | NO_BROKER | NO_EXECUTION | NO_STRATEGY_CHANGE | "
    "WATCHLIST_APPEND_ONLY"
)

DEFAULT_ROOT = Path(".")
WATCHLIST_FILE = "watchlist.txt"
PROPOSAL_FILE = "tae_watchlist_proposal.json"
BACKUP_DIR = "backups"
PROMOTION_JSON = "tae_watchlist_promotion.json"
PROMOTION_MD = "TAE_WATCHLIST_PROMOTION_SUMMARY.md"
MAX_ADDITIONS = 10


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _read_watchlist(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [
        line.strip().upper()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _load_proposal(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing proposal: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Proposal root must be object")
    return payload


def _recommended_tickers(proposal: dict[str, Any]) -> list[str]:
    recs = proposal.get("recommended_additions_max_10") or []
    tickers: list[str] = []
    for item in recs:
        if isinstance(item, dict):
            ticker = str(item.get("ticker") or "").strip().upper()
        else:
            ticker = str(item).strip().upper()
        if ticker:
            tickers.append(ticker)
    return tickers[:MAX_ADDITIONS]


def build_promotion_plan(root: Path) -> dict[str, Any]:
    watchlist_path = root / WATCHLIST_FILE
    proposal_path = root / PROPOSAL_FILE
    proposal = _load_proposal(proposal_path)

    existing = _read_watchlist(watchlist_path)
    existing_set = set(existing)
    recommended = _recommended_tickers(proposal)

    additions: list[str] = []
    skipped_duplicates: list[str] = []
    for ticker in recommended:
        if ticker in existing_set or ticker in additions:
            skipped_duplicates.append(ticker)
            continue
        additions.append(ticker)

    new_watchlist = existing + additions
    stamp = _utc_now().strftime("%Y%m%d_%H%M%S")
    backup_path = root / BACKUP_DIR / f"watchlist_{stamp}.txt"
    rollback_command = f"cp {backup_path} {watchlist_path}"

    rec_details = []
    for item in proposal.get("recommended_additions_max_10") or []:
        if isinstance(item, dict):
            rec_details.append(item)

    return {
        "schema": "tae.watchlist_promotion.v1",
        "mode": "GOVERNED_CONFIG_CHANGE",
        "generated_at": _utc_now().isoformat(),
        "safety_mode": SAFETY_BANNER,
        "proposal_path": str(proposal_path),
        "proposal_generated_at": proposal.get("generated_at"),
        "proposal_global_data_sufficient": (proposal.get("summary") or {}).get(
            "global_data_sufficient"
        ),
        "watchlist_path": str(watchlist_path),
        "old_count": len(existing),
        "new_count": len(new_watchlist),
        "additions": additions,
        "skipped_duplicates": skipped_duplicates,
        "recommended_from_proposal": recommended,
        "existing_watchlist": existing,
        "new_watchlist": new_watchlist,
        "backup_path": str(backup_path),
        "rollback_command": rollback_command,
        "restart_needed": False,
        "restart_reason": (
            "live_bot.py calls load_watchlist() each signal cycle (~60s); new tickers "
            "are included on the next cycle without restart. Optional restart only if "
            "bot process is stuck or operator wants immediate rescan."
        ),
        "addition_details": [
            item
            for item in rec_details
            if str(item.get("ticker", "")).upper() in additions
        ],
    }


def _render_markdown(plan: dict[str, Any], *, applied: bool) -> str:
    status = "APPLIED" if applied else "DRY_RUN"
    lines = [
        "# TAE Watchlist Promotion Summary",
        "",
        f"**Status:** {status}",
        f"**Generated:** {plan['generated_at']}",
        f"**Safety:** {plan['safety_mode']}",
        "",
        "## Counts",
        "",
        f"- Old count: **{plan['old_count']}**",
        f"- New count: **{plan['new_count']}**",
        f"- Additions: **{len(plan['additions'])}**",
        f"- Skipped duplicates: **{len(plan['skipped_duplicates'])}**",
        "",
        "## Source proposal",
        "",
        f"- File: `{plan['proposal_path']}`",
        f"- Generated: {plan.get('proposal_generated_at')}",
        f"- Global data sufficient: {plan.get('proposal_global_data_sufficient')}",
        "",
        "## Additions",
        "",
    ]
    if plan["additions"]:
        for ticker in plan["additions"]:
            lines.append(f"- {ticker}")
    else:
        lines.append("- *(none)*")

    if plan["skipped_duplicates"]:
        lines.extend(["", "## Skipped duplicates", ""])
        for ticker in plan["skipped_duplicates"]:
            lines.append(f"- {ticker}")

    lines.extend(
        [
            "",
            "## Backup & rollback",
            "",
            f"- Backup path: `{plan['backup_path']}`",
            f"- Rollback: `{plan['rollback_command']}`",
            "",
            "## Restart",
            "",
            f"- Restart needed: **{'yes' if plan['restart_needed'] else 'no'}**",
            f"- Note: {plan.get('restart_reason', '')}",
            "",
            "## Governance",
            "",
            "- Existing tickers preserved in original order",
            "- Append-only — no removals",
            "- live_bot.py not modified",
        ]
    )
    return "\n".join(lines) + "\n"


def apply_promotion(plan: dict[str, Any], root: Path) -> None:
    watchlist_path = root / WATCHLIST_FILE
    backup_path = Path(plan["backup_path"])

    backup_path.parent.mkdir(parents=True, exist_ok=True)
    if watchlist_path.is_file():
        backup_path.write_text(
            watchlist_path.read_text(encoding="utf-8", errors="replace"),
            encoding="utf-8",
        )
    else:
        backup_path.write_text("", encoding="utf-8")

    new_content = "\n".join(plan["new_watchlist"]) + "\n"
    watchlist_path.write_text(new_content, encoding="utf-8")

    after = _read_watchlist(watchlist_path)
    if after != plan["new_watchlist"]:
        raise RuntimeError("Watchlist verification failed after apply")


def main() -> int:
    parser = argparse.ArgumentParser(description="TAE governed watchlist promotion")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Plan only, no file writes")
    group.add_argument("--apply", action="store_true", help="Apply promotion with backup")
    parser.add_argument("--root", default=".", help="Project root")
    args = parser.parse_args()

    root = Path(args.root)
    plan = build_promotion_plan(root)
    applied = False

    if args.apply:
        apply_promotion(plan, root)
        applied = True
        plan["applied_at"] = _utc_now().isoformat()
        plan["status"] = "APPLIED"
    else:
        plan["status"] = "DRY_RUN"

    (root / PROMOTION_JSON).write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (root / PROMOTION_MD).write_text(
        _render_markdown(plan, applied=applied),
        encoding="utf-8",
    )

    print("===== TAE WATCHLIST PROMOTION =====")
    print(f"Mode: {plan['status']}")
    print(f"Old count: {plan['old_count']} → New count: {plan['new_count']}")
    print(f"Additions ({len(plan['additions'])}): {', '.join(plan['additions']) or '(none)'}")
    if plan["skipped_duplicates"]:
        print(f"Skipped duplicates: {', '.join(plan['skipped_duplicates'])}")
    if applied:
        print(f"Backup: {plan['backup_path']}")
        print(f"Rollback: {plan['rollback_command']}")
    print(f"Restart needed: {'yes' if plan['restart_needed'] else 'no'}")
    print(f"Output: {PROMOTION_JSON}, {PROMOTION_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
