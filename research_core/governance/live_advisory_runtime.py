"""
TAE Live Advisory Runtime — Phase X Sprint X.8

CONTROLLED_INTEGRATION | ADVISORY_RISK_FILTER_ONLY

Read-only consumer of tae_live_advisory.json for live_bot.py.
TAE may block new BUY on RISK_ADVISORY only — never forces BUY or SELL.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ADVISORY_PATH = Path("tae_live_advisory.json")
DEFAULT_MAX_AGE_HOURS = 24.0

VALID_ACTIONS = frozenset(
    {
        "NO_ACTION",
        "RISK_ADVISORY",
        "BUY_ADVISORY",
        "SELL_ADVISORY",
    }
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
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


@dataclass
class LiveAdvisoryRuntimeState:
    """In-memory view of tae_live_advisory.json for one bot cycle."""

    path: Path
    load_status: str  # ok | missing | invalid | stale
    action: str
    confidence: int | None = None
    generated_at: datetime | None = None
    age_hours: float | None = None
    stale_block_buy: bool = False
    warning: str | None = None
    blockers: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    payload: dict[str, Any] | None = None

    @property
    def is_usable(self) -> bool:
        return self.load_status == "ok" and self.payload is not None


def _extract_stale_block_buy(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    if _coerce_bool(payload.get("stale_block_buy")):
        return True
    runtime = payload.get("runtime_snapshot")
    if isinstance(runtime, dict) and _coerce_bool(runtime.get("stale_block_buy")):
        return True
    advisory = payload.get("advisory")
    if isinstance(advisory, dict) and _coerce_bool(advisory.get("stale_block_buy")):
        return True
    return False


def load_live_advisory(
    path: Path | str | None = None,
    *,
    max_age_hours: float | None = None,
    now: datetime | None = None,
) -> LiveAdvisoryRuntimeState:
    """
    Load tae_live_advisory.json without side effects.

    Missing / invalid / stale files fall back SAFE: action=NO_ACTION unless
    stale_block_buy=true is explicitly set in the payload (when readable).
    """
    advisory_path = Path(path or DEFAULT_ADVISORY_PATH)
    if max_age_hours is None:
        env_age = os.getenv("TAE_ADVISORY_MAX_AGE_HOURS", "").strip()
        max_age_hours = float(env_age) if env_age else DEFAULT_MAX_AGE_HOURS

    current = now or datetime.now(timezone.utc)

    if not advisory_path.is_file():
        return LiveAdvisoryRuntimeState(
            path=advisory_path,
            load_status="missing",
            action="NO_ACTION",
            warning="tae_live_advisory.json missing — live bot unchanged (SAFE fallback)",
        )

    try:
        payload = json.loads(advisory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return LiveAdvisoryRuntimeState(
            path=advisory_path,
            load_status="invalid",
            action="NO_ACTION",
            warning=f"tae_live_advisory.json invalid JSON — SAFE fallback ({exc})",
        )
    except OSError as exc:
        return LiveAdvisoryRuntimeState(
            path=advisory_path,
            load_status="invalid",
            action="NO_ACTION",
            warning=f"tae_live_advisory.json unreadable — SAFE fallback ({exc})",
        )

    if not isinstance(payload, dict):
        return LiveAdvisoryRuntimeState(
            path=advisory_path,
            load_status="invalid",
            action="NO_ACTION",
            warning="tae_live_advisory.json root must be object — SAFE fallback",
        )

    stale_block_buy = _extract_stale_block_buy(payload)
    generated_at = _parse_timestamp(payload.get("generated_at"))
    age_hours = None
    load_status = "ok"
    warning = None

    if generated_at is not None:
        age_hours = (current - generated_at).total_seconds() / 3600.0
        if age_hours > max_age_hours:
            load_status = "stale"
            warning = (
                f"tae_live_advisory.json stale ({age_hours:.1f}h > {max_age_hours:.1f}h) "
                "— SAFE fallback unless stale_block_buy=true"
            )
    else:
        load_status = "stale"
        warning = "tae_live_advisory.json missing generated_at — treated as stale"

    advisory = payload.get("advisory")
    if not isinstance(advisory, dict):
        return LiveAdvisoryRuntimeState(
            path=advisory_path,
            load_status="invalid",
            action="NO_ACTION",
            stale_block_buy=stale_block_buy,
            warning="advisory section missing or invalid — SAFE fallback",
            payload=payload,
        )

    raw_action = str(advisory.get("action") or "NO_ACTION").strip().upper()
    action = raw_action if raw_action in VALID_ACTIONS else "NO_ACTION"
    if raw_action not in VALID_ACTIONS:
        warning = warning or f"Unknown advisory action '{raw_action}' — using NO_ACTION"

    confidence_raw = advisory.get("confidence")
    confidence = int(confidence_raw) if confidence_raw is not None else None

    blockers = [str(item) for item in (advisory.get("blockers") or []) if item]
    reasons = [str(item) for item in (advisory.get("reasons") or []) if item]

    if load_status != "ok":
        # Stale/missing generated_at: do not apply RISK from stale payload unless flag set.
        action = "NO_ACTION"

    return LiveAdvisoryRuntimeState(
        path=advisory_path,
        load_status=load_status,
        action=action,
        confidence=confidence,
        generated_at=generated_at,
        age_hours=age_hours,
        stale_block_buy=stale_block_buy,
        warning=warning,
        blockers=blockers,
        reasons=reasons,
        payload=payload,
    )


def get_advisory_action(state: LiveAdvisoryRuntimeState) -> str:
    """Return normalized advisory action for the current cycle."""
    return state.action if state.action in VALID_ACTIONS else "NO_ACTION"


def should_block_new_buy(state: LiveAdvisoryRuntimeState) -> tuple[bool, str]:
    """
    True only when new BUY orders must be blocked by TAE risk filter.

    - RISK_ADVISORY (valid file): block new BUY
    - missing/invalid/stale: block only if stale_block_buy=true in payload
    - BUY_ADVISORY / SELL_ADVISORY / NO_ACTION: never block via TAE
    """
    if state.load_status == "ok":
        if get_advisory_action(state) == "RISK_ADVISORY":
            reason = "TAE RISK_ADVISORY — new BUY blocked"
            if state.blockers:
                reason = f"{reason}: {state.blockers[0]}"
            return True, reason
        return False, ""

    if state.stale_block_buy:
        return (
            True,
            f"TAE advisory {state.load_status} with stale_block_buy=true — new BUY blocked",
        )

    return False, ""


def advisory_runtime_summary(state: LiveAdvisoryRuntimeState) -> str:
    """Single-line summary for live_bot logging."""
    parts = [
        f"status={state.load_status}",
        f"action={get_advisory_action(state)}",
    ]
    if state.confidence is not None:
        parts.append(f"confidence={state.confidence}")
    if state.age_hours is not None:
        parts.append(f"age_h={state.age_hours:.1f}")
    if state.stale_block_buy:
        parts.append("stale_block_buy=true")
    block, reason = should_block_new_buy(state)
    parts.append(f"block_new_buy={block}")
    if reason:
        parts.append(f"block_reason={reason}")
    if state.warning:
        parts.append(f"warning={state.warning}")
    return " | ".join(parts)


def _self_check() -> int:
    """Minimal runtime checks for demo/validation."""
    errors: list[str] = []

    risk_state = LiveAdvisoryRuntimeState(
        path=DEFAULT_ADVISORY_PATH,
        load_status="ok",
        action="RISK_ADVISORY",
        blockers=["test blocker"],
    )
    block, _ = should_block_new_buy(risk_state)
    if not block:
        errors.append("RISK_ADVISORY should block new BUY")

    for action in ("NO_ACTION", "BUY_ADVISORY", "SELL_ADVISORY"):
        st = LiveAdvisoryRuntimeState(
            path=DEFAULT_ADVISORY_PATH,
            load_status="ok",
            action=action,
        )
        if should_block_new_buy(st)[0]:
            errors.append(f"{action} should not block new BUY")

    missing = LiveAdvisoryRuntimeState(
        path=DEFAULT_ADVISORY_PATH,
        load_status="missing",
        action="NO_ACTION",
    )
    if should_block_new_buy(missing)[0]:
        errors.append("missing advisory should not block BUY without stale_block_buy")

    stale_flag = LiveAdvisoryRuntimeState(
        path=DEFAULT_ADVISORY_PATH,
        load_status="stale",
        action="NO_ACTION",
        stale_block_buy=True,
    )
    if not should_block_new_buy(stale_flag)[0]:
        errors.append("stale with stale_block_buy=true should block BUY")

    live_state = load_live_advisory()
    summary = advisory_runtime_summary(live_state)
    print("load_live_advisory():", summary)

    if errors:
        print("SELF_CHECK FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("SELF_CHECK PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_check())
