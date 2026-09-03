"""
V5.1 Policy Shadow — Level 1 consolidation, observation phase.

CONNECTED_SHADOW_VALIDATION | OBSERVABILITY_ONLY | NO_EXECUTION | PAPER_ONLY

Logs where live_bot.py's static trading policy (fixed MAX_POSITIONS,
fixed entry threshold, binary BULL/BEAR regime, fixed Take-Profit/Stop-Loss)
would have decided differently from live_bot_v5_1.py's dynamic policy
(regime-adjusted MAX_POSITIONS, dynamic entry threshold, 3-way regime,
trailing-stop) on the exact same cycle — without ever blocking a BUY,
forcing a SELL, or touching portfolio.csv.

Maintains its own trailing-stop state file, completely separate from
portfolio.csv, so a bug here can never corrupt real trade state. The goal
is to build an evidence base (how often, how much the two policies would
diverge) before any decision to migrate live_bot.py onto the dynamic
policy — see docs/superpowers/specs (Level 1 consolidation) for context.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from core.entry_filter import get_dynamic_min_score_to_buy
from core.market_regime import get_market_regime as get_dynamic_market_regime
from core.market_regime import get_max_positions
from core.trailing import update_trailing_state

DEFAULT_EVENTS_PATH = Path("v51_policy_shadow_events.csv")
DEFAULT_TRAILING_STATE_PATH = Path("v51_shadow_trailing_state.csv")
MODE = "CONNECTED_SHADOW_VALIDATION"
LIVE_TRADING_IMPACT = "NONE"

CHECK_REGIME = "REGIME"
CHECK_MAX_POSITIONS = "MAX_POSITIONS"
CHECK_ENTRY_THRESHOLD = "ENTRY_THRESHOLD"
CHECK_EXIT_STRATEGY = "EXIT_STRATEGY"

VALID_CHECK_TYPES = frozenset(
    {CHECK_REGIME, CHECK_MAX_POSITIONS, CHECK_ENTRY_THRESHOLD, CHECK_EXIT_STRATEGY}
)

CSV_FIELDNAMES = (
    "timestamp",
    "check_type",
    "ticker",
    "live_value",
    "dynamic_value",
    "agree",
    "detail",
    "live_bot_cycle_id",
    "mode",
    "live_trading_impact",
)

_TRAILING_STATE_COLUMNS = ["Ticker", "Action", "Highest_Price", "Trailing_Active", "Trailing_Stop"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ShadowCheckEvent:
    check_type: str
    ticker: str
    live_value: str
    dynamic_value: str
    agree: bool
    detail: str = ""
    live_bot_cycle_id: str | None = None
    timestamp: str | None = None

    def to_row(self) -> dict[str, str]:
        if self.check_type not in VALID_CHECK_TYPES:
            raise ValueError(f"Invalid check_type: {self.check_type}")
        return {
            "timestamp": self.timestamp or _utc_now_iso(),
            "check_type": self.check_type,
            "ticker": str(self.ticker).strip().upper(),
            "live_value": str(self.live_value),
            "dynamic_value": str(self.dynamic_value),
            "agree": str(bool(self.agree)).lower(),
            "detail": self.detail,
            "live_bot_cycle_id": "" if self.live_bot_cycle_id is None else str(self.live_bot_cycle_id),
            "mode": MODE,
            "live_trading_impact": LIVE_TRADING_IMPACT,
        }


class PolicyShadowLedger:
    """Append-only CSV ledger for v5.1 policy-shadow observations."""

    def __init__(self, path: Path | str | None = None, *, warn_fn: Callable[[str], None] | None = None) -> None:
        self._path = Path(path or DEFAULT_EVENTS_PATH)
        self._warn_fn = warn_fn or (lambda msg: None)

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

    def append(self, event: ShadowCheckEvent) -> bool:
        """Append one event. Returns True on success; never raises."""
        try:
            self._ensure_header()
            row = event.to_row()
            with self._path.open("a", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
                writer.writerow(row)
            return True
        except Exception as exc:
            self._warn_fn(f"Policy shadow ledger write failed: {exc}")
            return False


_default_ledger: PolicyShadowLedger | None = None


def get_default_ledger(warn_fn: Callable[[str], None] | None = None) -> PolicyShadowLedger:
    global _default_ledger
    if _default_ledger is None or warn_fn is not None:
        _default_ledger = PolicyShadowLedger(warn_fn=warn_fn)
    return _default_ledger


def _load_trailing_state(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=_TRAILING_STATE_COLUMNS)
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=_TRAILING_STATE_COLUMNS)
    for col in _TRAILING_STATE_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[_TRAILING_STATE_COLUMNS]


def _save_trailing_state(df: pd.DataFrame, path: Path) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    df.to_csv(tmp_path, index=False)
    tmp_path.replace(path)


def _check_regime_and_position_cap(
    ledger: PolicyShadowLedger,
    positions: dict,
    live_regime: str,
    live_max_positions: int,
    cycle_id: str | None,
) -> None:
    dynamic_regime = get_dynamic_market_regime()
    dynamic_max_positions = get_max_positions(dynamic_regime)

    ledger.append(
        ShadowCheckEvent(
            check_type=CHECK_REGIME,
            ticker="MARKET",
            live_value=live_regime,
            dynamic_value=dynamic_regime,
            agree=(live_regime == dynamic_regime),
            detail="live: binary BULL/BEAR vs dynamic: 3-way regime with NEUTRAL band",
            live_bot_cycle_id=cycle_id,
        )
    )

    open_count = len(positions)
    live_would_block = open_count >= live_max_positions
    dynamic_would_block = open_count >= dynamic_max_positions

    ledger.append(
        ShadowCheckEvent(
            check_type=CHECK_MAX_POSITIONS,
            ticker="PORTFOLIO",
            live_value=str(live_max_positions),
            dynamic_value=str(dynamic_max_positions),
            agree=(live_would_block == dynamic_would_block),
            detail=(
                f"open_positions={open_count} "
                f"live_would_block_new_buy={live_would_block} "
                f"dynamic_would_block_new_buy={dynamic_would_block}"
            ),
            live_bot_cycle_id=cycle_id,
        )
    )


def _check_entry_threshold(
    ledger: PolicyShadowLedger,
    signals_df: pd.DataFrame | None,
    positions: dict,
    live_min_score: float,
    cycle_id: str | None,
) -> None:
    if signals_df is None or signals_df.empty:
        return

    dynamic_min_score = get_dynamic_min_score_to_buy()
    if dynamic_min_score == live_min_score:
        return

    candidates = signals_df[signals_df["Signal"] == "STRONG BUY"]

    for _, row in candidates.iterrows():
        ticker = row["Ticker"]
        if ticker in positions:
            continue

        score = pd.to_numeric(row.get("Score"), errors="coerce")
        if pd.isna(score):
            continue

        live_would_buy = score >= live_min_score
        dynamic_would_buy = score >= dynamic_min_score
        if live_would_buy == dynamic_would_buy:
            continue

        ledger.append(
            ShadowCheckEvent(
                check_type=CHECK_ENTRY_THRESHOLD,
                ticker=ticker,
                live_value=str(live_min_score),
                dynamic_value=str(dynamic_min_score),
                agree=False,
                detail=f"score={score} live_would_buy={live_would_buy} dynamic_would_buy={dynamic_would_buy}",
                live_bot_cycle_id=cycle_id,
            )
        )


def _check_exit_strategy(
    ledger: PolicyShadowLedger,
    signals_df: pd.DataFrame | None,
    positions: dict,
    tp_pct: float,
    sl_pct: float,
    cycle_id: str | None,
    trailing_state_path: Path,
) -> None:
    if not positions:
        # Nothing open: also drop any leftover shadow trailing state so a
        # future reopen of any of these tickers starts from a clean peak
        # instead of a stale one.
        if trailing_state_path.is_file():
            _save_trailing_state(pd.DataFrame(columns=_TRAILING_STATE_COLUMNS), trailing_state_path)
        return

    price_by_ticker: dict[str, float] = {}
    if signals_df is not None and not signals_df.empty:
        for _, row in signals_df.iterrows():
            price = pd.to_numeric(row.get("Price"), errors="coerce")
            if pd.notna(price) and price > 0:
                price_by_ticker[row["Ticker"]] = float(price)

    state = _load_trailing_state(trailing_state_path)

    for ticker, pos in positions.items():
        price = price_by_ticker.get(ticker)
        if price is None:
            # No fresh price for this ticker this cycle — skip rather than
            # simulate off a stale/guessed value.
            continue

        avg_price = float(pos["avg_price"])
        pnl_pct = ((price - avg_price) / avg_price) * 100 if avg_price else 0
        live_exit = pnl_pct >= tp_pct or pnl_pct <= sl_pct

        ticker_mask = state["Ticker"].astype(str).str.upper() == str(ticker).upper()
        if not ticker_mask.any():
            state = pd.concat(
                [
                    state,
                    pd.DataFrame(
                        [
                            {
                                "Ticker": ticker,
                                "Action": "BUY",
                                "Highest_Price": None,
                                "Trailing_Active": False,
                                "Trailing_Stop": None,
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )

        state, would_sell, trailing_stop = update_trailing_state(state, ticker, price, avg_price)

        if live_exit != would_sell:
            ledger.append(
                ShadowCheckEvent(
                    check_type=CHECK_EXIT_STRATEGY,
                    ticker=ticker,
                    live_value=f"fixed_tp{tp_pct}_sl{sl_pct}:{'EXIT' if live_exit else 'HOLD'}",
                    dynamic_value=f"trailing:{'EXIT' if would_sell else 'HOLD'}",
                    agree=False,
                    detail=f"pnl={pnl_pct:.2f}% price={price:.2f} trailing_stop={trailing_stop}",
                    live_bot_cycle_id=cycle_id,
                )
            )

    # Drop shadow trailing state for any ticker no longer open — otherwise a
    # closed-then-reopened ticker would inherit a stale Highest_Price from
    # its previous round, the same class of bug fixed elsewhere in this
    # codebase for the real portfolio.
    state = state[state["Ticker"].astype(str).str.upper().isin({t.upper() for t in positions})]
    _save_trailing_state(state, trailing_state_path)


def run_v51_policy_shadow(
    signals_df: pd.DataFrame | None,
    positions: dict,
    *,
    live_regime: str,
    live_max_positions: int,
    live_min_score_to_buy: float,
    live_take_profit_pct: float,
    live_stop_loss_pct: float,
    live_bot_cycle_id: str | None = None,
    warn_fn: Callable[[str], None] | None = None,
    trailing_state_path: Path | str | None = None,
) -> None:
    """Log where live_bot.py's static policy and live_bot_v5_1.py's dynamic
    policy would have diverged this cycle. Observation only: never raises
    to the caller, never blocks a BUY, never forces a SELL, never touches
    portfolio.csv or signals_df.
    """
    ledger = get_default_ledger(warn_fn)
    warn = warn_fn or (lambda _msg: None)

    try:
        _check_regime_and_position_cap(ledger, positions, live_regime, live_max_positions, live_bot_cycle_id)
        _check_entry_threshold(ledger, signals_df, positions, live_min_score_to_buy, live_bot_cycle_id)
        _check_exit_strategy(
            ledger,
            signals_df,
            positions,
            live_take_profit_pct,
            live_stop_loss_pct,
            live_bot_cycle_id,
            Path(trailing_state_path or DEFAULT_TRAILING_STATE_PATH),
        )
    except Exception as exc:
        warn(f"V5.1 policy shadow error (non-blocking): {exc}")


def _self_check() -> int:
    import tempfile

    errors: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        events_path = Path(tmp) / "demo_shadow_events.csv"
        trailing_path = Path(tmp) / "demo_trailing_state.csv"
        ledger = PolicyShadowLedger(events_path)

        if not ledger.append(
            ShadowCheckEvent(
                check_type=CHECK_REGIME,
                ticker="MARKET",
                live_value="BULL",
                dynamic_value="NEUTRAL",
                agree=False,
                detail="demo",
                live_bot_cycle_id="demo-cycle-1",
            )
        ):
            errors.append("demo event write failed")

        if not events_path.is_file():
            errors.append("demo CSV not created")
        else:
            with events_path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                if reader.fieldnames != list(CSV_FIELDNAMES):
                    errors.append(f"CSV header mismatch: {reader.fieldnames}")
                rows = list(reader)
                if len(rows) != 1:
                    errors.append(f"expected 1 demo row, got {len(rows)}")

        # Failure-safe: write errors must not raise to caller.
        class _BrokenLedger(PolicyShadowLedger):
            def _ensure_header(self) -> None:
                raise OSError("simulated ledger failure")

        broken = _BrokenLedger(events_path)
        broken._warn_fn = lambda _msg: None
        try:
            ok = broken.append(
                ShadowCheckEvent(
                    check_type=CHECK_REGIME, ticker="FAIL", live_value="x", dynamic_value="y", agree=False
                )
            )
            if ok:
                errors.append("broken ledger should return False on failure")
        except Exception as exc:
            errors.append(f"failure-safe raised unexpectedly: {exc}")

        # run_v51_policy_shadow must never raise even with bad/empty inputs.
        try:
            run_v51_policy_shadow(
                signals_df=None,
                positions={},
                live_regime="BULL",
                live_max_positions=12,
                live_min_score_to_buy=90,
                live_take_profit_pct=5,
                live_stop_loss_pct=-3,
                live_bot_cycle_id="demo-cycle-2",
                warn_fn=lambda _msg: None,
                trailing_state_path=trailing_path,
            )
        except Exception as exc:
            errors.append(f"run_v51_policy_shadow raised on empty input: {exc}")

    if errors:
        print("SELF_CHECK FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("SELF_CHECK PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_check())
