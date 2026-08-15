#!/usr/bin/env python3
"""TAE live promotion lock audit — Phase 9 enforcement documentation."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_MD = Path("TAE_LIVE_PROMOTION_LOCK_REPORT.md")
PROMOTION_JSON = Path("runtime_outputs/full_paper_cycle/promotion_gate.json")
FORBIDDEN_PROMOTION = re.compile(r"PROMOTE_TO_LIVE(?!_CANDIDATE)")

SCAN_ROOTS = (
    Path("."),
)
SCAN_GLOBS = ("tae_*.py", "tae_cli/**/*.py")
EXCLUDE_DIRS = {".git", "venv", "__pycache__", "runtime_outputs", "core", "research_core"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def scan_forbidden_promotion_wording() -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for pattern in SCAN_GLOBS:
        for path in Path(".").glob(pattern):
            if any(part in EXCLUDE_DIRS for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for idx, line in enumerate(text.splitlines(), start=1):
                if FORBIDDEN_PROMOTION.search(line) and "DO_NOT_PROMOTE_TO_LIVE" not in line:
                    hits.append({"file": str(path), "line": str(idx), "text": line.strip()[:120]})
    return hits


def audit_promotion_gate(gate: dict[str, Any] | None) -> dict[str, Any]:
    gate = gate or {}
    recs = gate.get("recommendations") or []
    violations: list[str] = []
    for row in recs:
        rec = str(row.get("promotion_recommendation") or "")
        if rec == "PROMOTE_TO_LIVE":
            violations.append(f"{row.get('ticker')}/{row.get('action')}: forbidden PROMOTE_TO_LIVE")
        if row.get("live_promotion_allowed") is True:
            violations.append(f"{row.get('ticker')}: live_promotion_allowed=true")
    return {
        "gate_present": bool(gate),
        "live_promotion_allowed": gate.get("live_promotion_allowed"),
        "recommendation_counts": gate.get("recommendation_counts"),
        "violations": violations,
        "operator_approval_required_for_candidates": sum(
            1 for r in recs if r.get("operator_approval_required")
        ),
    }


def enforce_promotion_gate(gate: dict[str, Any]) -> dict[str, Any]:
    """Normalize gate to hard-lock policy."""
    gate["live_promotion_allowed"] = False
    gate["promotion_lock"] = {
        "schema": "tae_live_promotion_lock",
        "allowed_recommendations": [
            "PROMOTE_TO_LIVE_CANDIDATE",
            "CONTINUE_PAPER",
            "REJECT",
            "NEEDS_MORE_DATA",
        ],
        "forbidden_recommendations": ["PROMOTE_TO_LIVE"],
        "requires_30_day_paper_validation": True,
        "requires_operator_approval": True,
        "machine_live_promotion_allowed": False,
    }
    for row in gate.get("recommendations") or []:
        rec = str(row.get("promotion_recommendation") or "")
        if rec == "PROMOTE_TO_LIVE":
            row["promotion_recommendation"] = "PROMOTE_TO_LIVE_CANDIDATE"
            row["promotion_lock_applied"] = True
        row["live_promotion_allowed"] = False
        if row.get("promotion_recommendation") == "PROMOTE_TO_LIVE_CANDIDATE":
            row["operator_approval_required"] = True
            row["requires_30_day_paper_complete"] = True
    return gate


def run_live_promotion_lock_audit(*, rewrite_gate: bool = True) -> dict[str, Any]:
    gate = load_json(PROMOTION_JSON) or {}
    if rewrite_gate and gate:
        gate = enforce_promotion_gate(gate)
        PROMOTION_JSON.parent.mkdir(parents=True, exist_ok=True)
        PROMOTION_JSON.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")

    wording_hits = scan_forbidden_promotion_wording()
    gate_audit = audit_promotion_gate(gate)

    report = {
        "generated_at": _now(),
        "lock_enforced": True,
        "machine_live_promotion_allowed": False,
        "allowed_wording": "PROMOTE_TO_LIVE_CANDIDATE only",
        "gate_audit": gate_audit,
        "forbidden_wording_hits_in_tae_py": wording_hits,
        "pass": not gate_audit.get("violations") and gate.get("live_promotion_allowed") is False,
    }

    lines = [
        "# TAE Live Promotion Lock Report",
        "",
        f"**Generated:** {report['generated_at']}",
        "",
        "## Policy",
        "",
        "- Machine outputs MUST keep `live_promotion_allowed=false`",
        "- Only `PROMOTE_TO_LIVE_CANDIDATE` is allowed (never bare `PROMOTE_TO_LIVE`)",
        "- 30-day PAPER validation must complete before operator review",
        "- Operator approval required outside automated cycle",
        "",
        "## Promotion gate audit",
        "",
        f"- Gate present: **{gate_audit.get('gate_present')}**",
        f"- live_promotion_allowed: **{gate_audit.get('live_promotion_allowed')}**",
        f"- Violations: **{len(gate_audit.get('violations') or [])}**",
        f"- Candidate recommendations requiring approval: **{gate_audit.get('operator_approval_required_for_candidates')}**",
        "",
        "## Forbidden wording scan (tae_*.py)",
        "",
    ]
    if wording_hits:
        lines.extend(f"- `{h['file']}:{h['line']}` — {h['text']}" for h in wording_hits[:20])
    else:
        lines.append("- No bare `PROMOTE_TO_LIVE` wording found in scanned TAE modules")
    lines.extend(["", f"**Lock status:** {'PASS' if report['pass'] else 'REVIEW_REQUIRED'}", ""])
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> int:
    print("===== TAE LIVE PROMOTION LOCK AUDIT =====")
    report = run_live_promotion_lock_audit()
    print("Lock enforced:", report["lock_enforced"])
    print("Gate violations:", len(report["gate_audit"].get("violations") or []))
    print("Wrote:", REPORT_MD)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
