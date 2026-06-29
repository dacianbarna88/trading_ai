"""
TAE Shadow Validation Ledger — Phase X Sprint X.9

CONNECTED_SHADOW_VALIDATION | OBSERVABILITY_ONLY | NO_EXECUTION

Append-only structured BUY evaluation events from live_bot.py.
Never executes trades, never modifies advisory, portfolio, or signals.
"""

from __future__ import annotations

import csv
import json
import logging
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

DEFAULT_EVENTS_PATH = Path("tae_shadow_validation_events.csv")
MODE = "CONNECTED_SHADOW_VALIDATION"
LIVE_TRADING_IMPACT = "NONE"

EVENT_BUY_BLOCKED_BY_TAE = "BUY_BLOCKED_BY_TAE"
EVENT_BUY_ALLOWED = "BUY_ALLOWED"
EVENT_BUY_SKIPPED_OTHER_REASON = "BUY_SKIPPED_OTHER_REASON"

VALID_EVENT_TYPES = frozenset(
    {
        EVENT_BUY_BLOCKED_BY_TAE,
        EVENT_BUY_ALLOWED,
        EVENT_BUY_SKIPPED_OTHER_REASON,
    }
)

CSV_FIELDNAMES = (
    "timestamp",
    "ticker",
    "event_type",
    "signal",
    "score",
    "price",
    "intended_trade_usd",
    "shares",
    "advisory_action",
    "advisory_confidence",
    "advisory_reasons",
    "advisory_blockers",
    "block_new_buy",
    "block_reason",
    "live_bot_cycle_id",
    "mode",
    "live_trading_impact",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class ShadowBuyEvent:
    ticker: str
    event_type: str
    signal: str | None = None
    score: float | None = None
    price: float | None = None
    intended_trade_usd: float | None = None
    shares: float | None = None
    advisory_action: str | None = None
    advisory_confidence: int | None = None
    advisory_reasons: list[str] | None = None
    advisory_blockers: list[str] | None = None
    block_new_buy: bool | None = None
    block_reason: str | None = None
    live_bot_cycle_id: str | None = None
    timestamp: str | None = None

    def to_row(self) -> dict[str, str]:
        if self.event_type not in VALID_EVENT_TYPES:
            raise ValueError(f"Invalid event_type: {self.event_type}")
        return {
            "timestamp": self.timestamp or _utc_now_iso(),
            "ticker": str(self.ticker).strip().upper(),
            "event_type": self.event_type,
            "signal": "" if self.signal is None else str(self.signal),
            "score": "" if self.score is None else str(self.score),
            "price": "" if self.price is None else str(self.price),
            "intended_trade_usd": ""
            if self.intended_trade_usd is None
            else str(self.intended_trade_usd),
            "shares": "" if self.shares is None else str(self.shares),
            "advisory_action": "" if self.advisory_action is None else str(self.advisory_action),
            "advisory_confidence": ""
            if self.advisory_confidence is None
            else str(self.advisory_confidence),
            "advisory_reasons": _json_cell(self.advisory_reasons or []),
            "advisory_blockers": _json_cell(self.advisory_blockers or []),
            "block_new_buy": ""
            if self.block_new_buy is None
            else str(bool(self.block_new_buy)).lower(),
            "block_reason": "" if self.block_reason is None else str(self.block_reason),
            "live_bot_cycle_id": "" if self.live_bot_cycle_id is None else str(self.live_bot_cycle_id),
            "mode": MODE,
            "live_trading_impact": LIVE_TRADING_IMPACT,
        }


class ShadowValidationLedger:
    """Append-only CSV ledger for live BUY evaluation observability."""

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        warn_fn: Callable[[str], None] | None = None,
    ) -> None:
        self._path = Path(path or DEFAULT_EVENTS_PATH)
        self._warn_fn = warn_fn or (lambda msg: logger.warning("%s", msg))

    @property
    def path(self) -> Path:
        return self._path

    def _ensure_header(self) -> None:
        if self._path.is_file():
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()

    def append(self, event: ShadowBuyEvent) -> bool:
        """Append one event. Returns True on success; never raises."""
        try:
            self._ensure_header()
            row = event.to_row()
            with self._path.open("a", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
                writer.writerow(row)
            return True
        except Exception as exc:
            self._warn_fn(f"Shadow validation ledger write failed: {exc}")
            return False

    def log_event(
        self,
        *,
        ticker: str,
        event_type: str,
        signal: Any = None,
        score: Any = None,
        price: Any = None,
        intended_trade_usd: Any = None,
        shares: Any = None,
        advisory_state: Any = None,
        advisory_action: str | None = None,
        advisory_confidence: int | None = None,
        advisory_reasons: list[str] | None = None,
        advisory_blockers: list[str] | None = None,
        block_new_buy: bool | None = None,
        block_reason: str | None = None,
        live_bot_cycle_id: str | None = None,
    ) -> bool:
        if advisory_state is not None:
            if advisory_action is None:
                advisory_action = getattr(advisory_state, "action", None)
            if advisory_confidence is None:
                advisory_confidence = getattr(advisory_state, "confidence", None)
            if advisory_reasons is None:
                advisory_reasons = list(getattr(advisory_state, "reasons", []) or [])
            if advisory_blockers is None:
                advisory_blockers = list(getattr(advisory_state, "blockers", []) or [])

        event = ShadowBuyEvent(
            ticker=ticker,
            event_type=event_type,
            signal=None if signal is None else str(signal),
            score=_safe_float(score),
            price=_safe_float(price),
            intended_trade_usd=_safe_float(intended_trade_usd),
            shares=_safe_float(shares),
            advisory_action=advisory_action,
            advisory_confidence=advisory_confidence,
            block_new_buy=block_new_buy,
            block_reason=block_reason,
            live_bot_cycle_id=live_bot_cycle_id,
            advisory_reasons=advisory_reasons,
            advisory_blockers=advisory_blockers,
        )
        return self.append(event)


_default_ledger: ShadowValidationLedger | None = None


def get_default_ledger(warn_fn: Callable[[str], None] | None = None) -> ShadowValidationLedger:
    global _default_ledger
    if _default_ledger is None or warn_fn is not None:
        _default_ledger = ShadowValidationLedger(warn_fn=warn_fn)
    return _default_ledger


def log_buy_blocked_by_tae(
    *,
    ticker: str,
    signal: Any,
    score: Any,
    price: Any,
    advisory_state: Any,
    block_reason: str,
    live_bot_cycle_id: str | None,
    warn_fn: Callable[[str], None] | None = None,
) -> bool:
    return get_default_ledger(warn_fn).log_event(
        ticker=ticker,
        event_type=EVENT_BUY_BLOCKED_BY_TAE,
        signal=signal,
        score=score,
        price=price,
        advisory_state=advisory_state,
        block_new_buy=True,
        block_reason=block_reason,
        live_bot_cycle_id=live_bot_cycle_id,
    )


def log_buy_allowed(
    *,
    ticker: str,
    signal: Any,
    score: Any,
    price: Any,
    intended_trade_usd: Any,
    shares: Any | None,
    advisory_state: Any,
    block_new_buy: bool,
    live_bot_cycle_id: str | None,
    warn_fn: Callable[[str], None] | None = None,
) -> bool:
    return get_default_ledger(warn_fn).log_event(
        ticker=ticker,
        event_type=EVENT_BUY_ALLOWED,
        signal=signal,
        score=score,
        price=price,
        intended_trade_usd=intended_trade_usd,
        shares=shares,
        advisory_state=advisory_state,
        block_new_buy=block_new_buy,
        block_reason=None,
        live_bot_cycle_id=live_bot_cycle_id,
    )


def log_buy_skipped_other_reason(
    *,
    ticker: str,
    signal: Any,
    score: Any,
    price: Any,
    block_reason: str,
    advisory_state: Any,
    block_new_buy: bool,
    live_bot_cycle_id: str | None,
    warn_fn: Callable[[str], None] | None = None,
) -> bool:
    return get_default_ledger(warn_fn).log_event(
        ticker=ticker,
        event_type=EVENT_BUY_SKIPPED_OTHER_REASON,
        signal=signal,
        score=score,
        price=price,
        advisory_state=advisory_state,
        block_new_buy=block_new_buy,
        block_reason=block_reason,
        live_bot_cycle_id=live_bot_cycle_id,
    )


def _self_check() -> int:
    errors: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "demo_shadow_events.csv"
        ledger = ShadowValidationLedger(tmp_path)

        class _FakeAdvisory:
            action = "RISK_ADVISORY"
            confidence = 53
            reasons = ["demo reason"]
            blockers = ["demo blocker"]

        adv = _FakeAdvisory()

        if not ledger.log_event(
            ticker="SPY",
            event_type=EVENT_BUY_BLOCKED_BY_TAE,
            signal="STRONG BUY",
            score=95,
            price=540.1,
            advisory_state=adv,
            block_new_buy=True,
            block_reason="TAE RISK_ADVISORY — demo",
            live_bot_cycle_id="demo-cycle-1",
        ):
            errors.append("BUY_BLOCKED_BY_TAE demo write failed")

        if not ledger.log_event(
            ticker="AAPL",
            event_type=EVENT_BUY_ALLOWED,
            signal="STRONG BUY",
            score=100,
            price=210.5,
            intended_trade_usd=500.0,
            shares=2.3753,
            advisory_state=adv,
            block_new_buy=False,
            live_bot_cycle_id="demo-cycle-1",
        ):
            errors.append("BUY_ALLOWED demo write failed")

        if not tmp_path.is_file():
            errors.append("demo CSV not created")
        else:
            with tmp_path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                if reader.fieldnames != list(CSV_FIELDNAMES):
                    errors.append(f"CSV header mismatch: {reader.fieldnames}")
                rows = list(reader)
                if len(rows) != 2:
                    errors.append(f"expected 2 demo rows, got {len(rows)}")

        # Failure-safe: write errors must not raise to caller
        class _BrokenLedger(ShadowValidationLedger):
            def _ensure_header(self) -> None:
                raise OSError("simulated ledger failure")

        broken = _BrokenLedger(tmp_path)
        broken._warn_fn = lambda _msg: None
        try:
            ok = broken.append(ShadowBuyEvent(ticker="FAIL", event_type=EVENT_BUY_ALLOWED))
            if ok:
                errors.append("broken ledger should return False on failure")
        except Exception as exc:
            errors.append(f"failure-safe raised unexpectedly: {exc}")

    real_path = DEFAULT_EVENTS_PATH
    if real_path.is_file():
        print(f"Real ledger exists: {real_path} (self-check did not modify it)")
    else:
        print(f"Real ledger not present yet: {real_path}")

    if errors:
        print("SELF_CHECK FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("SELF_CHECK PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_check())
