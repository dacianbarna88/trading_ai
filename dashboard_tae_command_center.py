"""
TAE Dashboard Command Center — UI / OBSERVABILITY ONLY

Read-only consumer of TAE ecosystem artifacts for dashboard_v2.py.
Does not modify live_bot.py, portfolio.csv, live_signals.csv, or execute trades.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(".").resolve()
REVIEW_SCRIPT = "tae_full_ecosystem_review.sh"

ARTIFACT_PATHS = {
    "ecosystem_review_json": "tae_full_ecosystem_review.json",
    "ecosystem_review_md": "tae_full_ecosystem_review.md",
    "accounting_snapshot": "tae_accounting_snapshot.json",
    "live_advisory": "tae_live_advisory.json",
    "shadow_summary": "tae_shadow_validation_summary.json",
    "shadow_events": "tae_shadow_validation_events.csv",
    "advisory_index": "tae_advisory_index.json",
    "portfolio_reconciliation": "tae_portfolio_reconciliation.json",
    "execution_integrity": "tae_execution_integrity_audit.json",
    "portfolio": "portfolio.csv",
    "live_signals": "live_signals.csv",
    "project_book": "PROJECT_BOOK.md",
    "session_start": "SESSION_START.md",
    "bot_status": "bot_status.txt",
    "session_guard_log": "market_session_guard.log",
}


def _safe_read_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.is_file():
        return None, "MISSING"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, "INVALID_JSON"
    except OSError:
        return None, "READ_ERROR"
    if not isinstance(payload, dict):
        return None, "INVALID_ROOT"
    return payload, "OK"


def _safe_read_text(path: Path, *, tail_lines: int | None = None) -> tuple[str, str]:
    if not path.is_file():
        return "", "MISSING"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", "READ_ERROR"
    if tail_lines is not None:
        lines = text.splitlines()
        text = "\n".join(lines[-tail_lines:])
    return text, "OK"


def _fmt(value: Any, *, prefix: str = "", suffix: str = "", missing: str = "NO_DATA") -> str:
    if value is None or value == "":
        return missing
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{prefix}{value:,.2f}{suffix}"
    if isinstance(value, int):
        return f"{prefix}{value:,}{suffix}"
    return str(value)


def _parse_session_start_fields(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    patterns = {
        "last_completed_sprint": r"\*\*Last completed sprint\*\*\s*\|\s*\*\*(.+?)\*\*",
        "next_allowed_sprint": r"## Next allowed sprint\s+\*\*(.+?)\*\*",
        "canonical_runtime": r"\*\*Canonical live runtime\*\*\s*\|\s*`(.+?)`",
        "mode": r"\*\*Mode\*\*\s*\|\s*(.+?)\s*\|",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
        if match:
            out[key] = match.group(1).strip()
    return out


def _parse_project_book_summary(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for label, pattern in {
        "latest_sprint": r"\*\*Latest sprint:\*\*\s*(.+)",
        "governance_mode": r"\*\*Governance mode:\*\*\s*(.+)",
        "canonical_runtime": r"\*\*Canonical runtime:\*\*\s*`(.+?)`",
    }.items():
        match = re.search(pattern, text)
        if match:
            out[label] = match.group(1).strip()
    arch_match = re.search(
        r"## 2\. Current TAE Architecture\s+```(.*?)```",
        text,
        re.DOTALL,
    )
    if arch_match:
        out["architecture_snippet"] = arch_match.group(1).strip()[:1200]
    return out


@dataclass
class TAECommandCenterContext:
    """Aggregated read-only view for the command center UI."""

    review: dict[str, Any] = field(default_factory=dict)
    review_status: str = "MISSING"
    accounting: dict[str, Any] = field(default_factory=dict)
    accounting_status: str = "MISSING"
    advisory: dict[str, Any] = field(default_factory=dict)
    advisory_status: str = "MISSING"
    shadow: dict[str, Any] = field(default_factory=dict)
    shadow_status: str = "MISSING"
    reconciliation: dict[str, Any] = field(default_factory=dict)
    reconciliation_status: str = "MISSING"
    integrity_audit: dict[str, Any] = field(default_factory=dict)
    integrity_status: str = "MISSING"
    bot_status: str = "NO_DATA"
    session_guard_tail: str = ""
    session_start: dict[str, str] = field(default_factory=dict)
    project_book: dict[str, str] = field(default_factory=dict)
    project_book_text: str = ""
    session_start_text: str = ""
    artifact_status: dict[str, str] = field(default_factory=dict)

    @property
    def runtime(self) -> dict[str, Any]:
        return self.review.get("A_runtime_status") or {}

    @property
    def market(self) -> dict[str, Any]:
        return self.review.get("Market_Readiness") or {}

    @property
    def mor(self) -> dict[str, Any]:
        return self.review.get("Market_Open_Readiness") or {}

    @property
    def financial(self) -> dict[str, Any]:
        if self.accounting.get("corrected_total_trading_pnl") is not None:
            return {
                "cash_available": self.accounting.get("cash_available"),
                "capital_deposits": self.accounting.get("capital_deposits"),
                "corrected_total_pnl_excluding_cash_deposits": self.accounting.get(
                    "corrected_total_trading_pnl"
                ),
                "corrected_realized_pnl": self.accounting.get("corrected_realized_pnl"),
                "trading_unrealized_pnl": self.accounting.get("corrected_unrealized_pnl"),
                "unrealized_pnl": self.accounting.get("corrected_unrealized_pnl"),
                "raw_total_pnl_including_cash_rows": self.accounting.get(
                    "raw_pnl_including_cash_rows"
                ),
                "accounting_adjustments": self.accounting.get("accounting_adjustments_excluded"),
                "account_value_corrected": self.accounting.get("account_value_corrected"),
                "data_quality_status": self.accounting.get("data_quality_status"),
                "reported_realized_pnl_stale": self.accounting.get("reported_realized_pnl_stale"),
            }
        return self.review.get("B_financial_status") or {}

    @property
    def drag(self) -> dict[str, Any]:
        if self.accounting.get("top_losers_corrected") is not None:
            return {
                "top_losing_trades": self.accounting.get("top_losers_corrected") or [],
                "top_winning_trades": self.accounting.get("top_winners_corrected") or [],
                "top_drag_corrected": self.accounting.get("top_drag_corrected"),
            }
        return self.review.get("Performance_Drag_Analysis") or {}

    @property
    def advisory_section(self) -> dict[str, Any]:
        return self.review.get("D_tae_advisory") or {}

    @property
    def shadow_section(self) -> dict[str, Any]:
        return self.review.get("E_shadow_validation") or {}

    @property
    def strategy(self) -> dict[str, Any]:
        return self.review.get("F_strategy_universe") or {}

    @property
    def execution(self) -> dict[str, Any]:
        return self.review.get("Execution_Integrity") or {}

    @property
    def signals(self) -> dict[str, Any]:
        return self.review.get("C_live_signals_today") or {}

    @property
    def final(self) -> dict[str, Any]:
        return self.review.get("J_final_verdict") or {}


def load_command_center_context(root: Path | str = PROJECT_ROOT) -> TAECommandCenterContext:
    root = Path(root)
    ctx = TAECommandCenterContext()
    status: dict[str, str] = {}

    review_path = root / ARTIFACT_PATHS["ecosystem_review_json"]
    review, review_st = _safe_read_json(review_path)
    ctx.review = review or {}
    ctx.review_status = review_st
    status["tae_full_ecosystem_review.json"] = review_st

    acct_path = root / ARTIFACT_PATHS["accounting_snapshot"]
    accounting, acct_st = _safe_read_json(acct_path)
    if accounting is None:
        try:
            from research_core.accounting.accounting_snapshot import build_accounting_snapshot

            accounting = build_accounting_snapshot(root)
            acct_st = "LIVE_BUILD"
        except Exception:
            accounting = {}
            acct_st = "ERROR"
    ctx.accounting = accounting or {}
    ctx.accounting_status = acct_st
    status["tae_accounting_snapshot.json"] = acct_st

    adv_path = root / ARTIFACT_PATHS["live_advisory"]
    advisory, adv_st = _safe_read_json(adv_path)
    ctx.advisory = advisory or {}
    ctx.advisory_status = adv_st
    status["tae_live_advisory.json"] = adv_st

    shadow_path = root / ARTIFACT_PATHS["shadow_summary"]
    shadow, shadow_st = _safe_read_json(shadow_path)
    ctx.shadow = shadow or {}
    ctx.shadow_status = shadow_st
    status["tae_shadow_validation_summary.json"] = shadow_st

    recon_path = root / ARTIFACT_PATHS["portfolio_reconciliation"]
    recon, recon_st = _safe_read_json(recon_path)
    ctx.reconciliation = recon or {}
    ctx.reconciliation_status = recon_st
    status["tae_portfolio_reconciliation.json"] = recon_st

    int_path = root / ARTIFACT_PATHS["execution_integrity"]
    integrity, int_st = _safe_read_json(int_path)
    ctx.integrity_audit = integrity or {}
    ctx.integrity_status = int_st
    status["tae_execution_integrity_audit.json"] = int_st

    bot_text, bot_st = _safe_read_text(root / ARTIFACT_PATHS["bot_status"])
    ctx.bot_status = bot_text.strip() or "NO_DATA"
    status["bot_status.txt"] = bot_st

    guard_tail, guard_st = _safe_read_text(
        root / ARTIFACT_PATHS["session_guard_log"], tail_lines=8
    )
    ctx.session_guard_tail = guard_tail
    status["market_session_guard.log"] = guard_st

    session_text, session_st = _safe_read_text(root / ARTIFACT_PATHS["session_start"])
    ctx.session_start_text = session_text
    ctx.session_start = _parse_session_start_fields(session_text)
    status["SESSION_START.md"] = session_st

    book_text, book_st = _safe_read_text(root / ARTIFACT_PATHS["project_book"])
    ctx.project_book_text = book_text
    ctx.project_book = _parse_project_book_summary(book_text)
    status["PROJECT_BOOK.md"] = book_st

    for name, rel in ARTIFACT_PATHS.items():
        if name in {
            "ecosystem_review_json",
            "live_advisory",
            "shadow_summary",
            "portfolio_reconciliation",
            "execution_integrity",
            "bot_status",
            "session_guard_log",
            "project_book",
            "session_start",
        }:
            continue
        path = root / rel
        if path.is_file():
            status[rel] = "OK"
        else:
            status[rel] = "MISSING"

    ctx.artifact_status = status
    return ctx


def run_full_ecosystem_review(root: Path | str = PROJECT_ROOT) -> tuple[bool, str]:
    """Run read-only ecosystem review script; return (success, output)."""
    root = Path(root)
    script = root / REVIEW_SCRIPT
    if not script.is_file():
        return False, f"MISSING: {REVIEW_SCRIPT}"
    try:
        result = subprocess.run(
            ["/bin/bash", str(script)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "Review script timed out after 180s"
    except OSError as exc:
        return False, f"Failed to run review: {exc}"

    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        return False, output or f"Exit code {result.returncode}"
    return True, output


def _metric_card(label: str, value: Any, *, help_text: str | None = None) -> None:
    st.metric(label, _fmt(value) if not isinstance(value, str) else (value or "NO_DATA"), help=help_text)


def render_refresh_bar(ctx: TAECommandCenterContext) -> None:
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        if st.button("🔄 Run Full Ecosystem Review", type="primary", key="tae_cc_refresh"):
            with st.spinner("Running tae_full_ecosystem_review.sh …"):
                ok, output = run_full_ecosystem_review()
            if ok:
                st.session_state["tae_cc_last_refresh_ok"] = True
                st.session_state["tae_cc_last_refresh_output"] = output[-4000:]
                st.success("Ecosystem review completed.")
                st.rerun()
            else:
                st.session_state["tae_cc_last_refresh_ok"] = False
                st.session_state["tae_cc_last_refresh_output"] = output[-4000:]
                st.error("Ecosystem review failed — dashboard still running.")
    with col_info:
        gen = ctx.review.get("generated_at") or ctx.advisory.get("generated_at")
        st.caption(
            f"UI/OBSERVABILITY ONLY · NO EXECUTION · "
            f"Review: {ctx.review_status} · Generated: {gen or 'NO_DATA'}"
        )
    if st.session_state.get("tae_cc_last_refresh_output"):
        with st.expander("Last review run output", expanded=not st.session_state.get("tae_cc_last_refresh_ok", True)):
            st.code(st.session_state["tae_cc_last_refresh_output"])


def _detect_sell_accounting_protection(root: Path) -> str:
    path = root / "live_bot.py"
    if not path.is_file():
        return "NO_DATA"
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return "NO_DATA"
    if 'if action in {"SELL", "DEPOSIT"}:' in source and "open BUY rows only" in source:
        return "ACTIVE"
    return "NOT_ACTIVE"


def render_command_center_metrics(ctx: TAECommandCenterContext) -> None:
    rt = ctx.runtime
    mor = ctx.mor
    fin = ctx.financial
    adv = ctx.advisory_section or (ctx.advisory.get("advisory") or {})
    sig = ctx.signals
    strat = ctx.strategy
    counts = strat.get("counts") or {}
    x9 = rt.get("x9_readiness") or ctx.shadow_section

    blocks = adv.get("blocks_new_buy")
    if blocks is None:
        blocks = mor.get("advisory_blocks_new_buy")
    if blocks is None:
        blocks = (rt.get("advisory_status") or {}).get("block_new_buy")

    sell_prot = mor.get("sell_accounting_protection")
    if not sell_prot:
        sell_prot = _detect_sell_accounting_protection(PROJECT_ROOT)

    x9_label = mor.get("x9_ledger_readiness") or x9.get("readiness_label", "NO_DATA")

    rows = [
        [
            ("Ecosystem Verdict", ctx.final.get("ecosystem_verdict", "NO_DATA")),
            ("Bot Status", rt.get("bot_status_effective") or ctx.bot_status),
            ("Dashboard Status", rt.get("dashboard_process_status", "NO_DATA")),
            ("Market Readiness", ctx.market.get("verdict") or mor.get("market_readiness_verdict", "NO_DATA")),
        ],
        [
            ("Advisory Action", adv.get("action", "NO_DATA")),
            ("Blocks New BUY", blocks),
            ("Cash", fin.get("cash_available")),
            ("Corrected Trading PnL", fin.get("corrected_total_pnl_excluding_cash_deposits")),
        ],
        [
            ("Corrected Realized PnL", fin.get("corrected_realized_pnl")),
            ("Corrected Unrealized PnL", fin.get("trading_unrealized_pnl")),
            ("Account Value (corrected)", fin.get("account_value_corrected")),
            ("Data Quality", fin.get("data_quality_status", "NO_DATA")),
        ],
        [
            ("STRONG BUY count", sig.get("strong_buy_count", "NO_DATA")),
            ("TAKE PROFIT count", sig.get("take_profit_count", "NO_DATA")),
            ("X.9 Ledger Status", x9_label),
            ("SELL Accounting Protection", sell_prot or "NO_DATA"),
        ],
        [
            ("Robust Strategies", counts.get("robust_shortlist_count", "NO_DATA")),
            ("Weak Strategies", counts.get("weak_shortlist_count", "NO_DATA")),
        ],
    ]

    for row in rows:
        cols = st.columns(4)
        for col, (label, value) in zip(cols, row):
            if not label:
                continue
            with col:
                _metric_card(label, value)
        if len(row) < 4:
            for col in cols[len(row) :]:
                col.empty()

    st.info(f"**Next Action:** {ctx.market.get('next_action_for_market_open') or ctx.final.get('next_action', 'NO_DATA')}")

    notes = ctx.market.get("notes") or []
    for note in notes[:2]:
        st.caption(f"ℹ️ {note}")


def render_financial_panel(ctx: TAECommandCenterContext) -> None:
    st.subheader("💰 Financial Performance")
    st.caption(
        f"Canonical source: tae_accounting_snapshot.json ({ctx.accounting_status}) · "
        f"Data quality: {ctx.accounting.get('data_quality_status', 'NO_DATA')}"
    )
    fin = ctx.financial
    acct = ctx.accounting
    drag = ctx.drag

    if not fin and not acct:
        st.warning("Accounting snapshot missing — run Full Ecosystem Review or tae_accounting_snapshot.py")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cash Available", _fmt(fin.get("cash_available"), prefix="$"))
    c2.metric(
        "Corrected Total PnL",
        _fmt(fin.get("corrected_total_pnl_excluding_cash_deposits"), prefix="$"),
    )
    c3.metric("Account Value (corrected)", _fmt(fin.get("account_value_corrected"), prefix="$"))
    c4.metric("Capital Deposits", _fmt(fin.get("capital_deposits"), prefix="$"))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Corrected Realized", _fmt(fin.get("corrected_realized_pnl"), prefix="$"))
    c6.metric("Corrected Unrealized", _fmt(fin.get("trading_unrealized_pnl"), prefix="$"))
    c7.metric("Raw PnL (incl. CASH)", _fmt(fin.get("raw_total_pnl_including_cash_rows"), prefix="$"))
    c8.metric("Data Quality", fin.get("data_quality_status", "NO_DATA"))

    if fin.get("accounting_adjustments"):
        st.warning(
            f"CASH/DEPOSIT distortion excluded from canonical PnL: "
            f"{fin.get('accounting_adjustments')} (raw column sum is not trading PnL)"
        )

    top_losers = drag.get("top_losing_trades") or []
    top_winners = drag.get("top_winning_trades") or []
    top_drag = drag.get("top_drag_corrected") or (top_losers[0] if top_losers else None)
    if top_drag:
        st.error(
            f"Top drag (corrected): **{top_drag.get('ticker')}** PnL {top_drag.get('pnl')} "
            f"({top_drag.get('reason', '')})"
        )
    col_w, col_l = st.columns(2)
    with col_w:
        if top_winners:
            st.markdown("**Top winners**")
            st.dataframe(pd.DataFrame(top_winners[:5]), width="stretch", hide_index=True)
        else:
            st.caption("Top winners: NO_DATA")
    with col_l:
        if top_losers:
            st.markdown("**Top losers / drag**")
            st.dataframe(pd.DataFrame(top_losers[:5]), width="stretch", hide_index=True)
        else:
            st.caption("Top losers: NO_DATA")

    warnings = fin.get("warnings") or []
    if warnings:
        with st.expander("Financial warnings", expanded=False):
            for w in warnings:
                st.write(f"• {w}")


def render_advisory_panel(ctx: TAECommandCenterContext) -> None:
    st.subheader("📡 TAE Advisory")
    adv = ctx.advisory_section
    live = ctx.advisory.get("advisory") or {}

    action = adv.get("action") or live.get("action", "NO_DATA")
    confidence = adv.get("confidence") if adv.get("confidence") is not None else live.get("confidence")
    blocks = adv.get("blocks_new_buy")
    if blocks is None:
        blocks = (ctx.runtime.get("advisory_status") or {}).get("block_new_buy")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Action", action)
    c2.metric("Confidence", confidence if confidence is not None else "NO_DATA")
    c3.metric("Block New BUY", _fmt(blocks))
    c4.metric(
        "Blocking / Info warnings",
        f"{adv.get('blocking_warnings_count', 0)} / {adv.get('informational_warnings_count', 0)}",
    )

    if action == "RISK_ADVISORY":
        st.error("**RISK_ADVISORY** — X.8 BUY gate **active**. New BUY orders blocked by TAE.")
    elif action == "SELL_ADVISORY":
        st.info("**SELL_ADVISORY** — informational only. Does **not** execute SELL; live bot SELL rules unchanged.")
    elif action == "BUY_ADVISORY":
        st.info("**BUY_ADVISORY** — supportive context only. No auto-buy.")
    elif action == "NO_ACTION":
        st.success("**NO_ACTION** — TAE does not block BUY via advisory.")

    col_r, col_b = st.columns(2)
    with col_r:
        reasons = adv.get("reasons") or live.get("reasons") or []
        with st.expander(f"Reasons ({len(reasons)})", expanded=False):
            for r in reasons[:20]:
                st.write(f"• {r}")
            if not reasons:
                st.caption("NO_DATA")
    with col_b:
        blockers = adv.get("blockers") or live.get("blockers") or []
        with st.expander(f"Blockers ({len(blockers)})", expanded=False):
            for b in blockers[:15]:
                st.write(f"• {b}")
            if not blockers:
                st.caption("(none)")

    bw = adv.get("blocking_warnings") or live.get("blocking_warnings") or []
    iw = adv.get("informational_warnings") or live.get("informational_warnings") or []
    if bw or iw:
        with st.expander("Warning breakdown", expanded=False):
            if bw:
                st.markdown("**Blocking warnings**")
                for w in bw:
                    st.write(f"🔴 {w}")
            if iw:
                st.markdown("**Informational warnings**")
                for w in iw[:10]:
                    st.write(f"ℹ️ {w}")


def render_shadow_panel(ctx: TAECommandCenterContext) -> None:
    st.subheader("🧪 Shadow Validation")
    sh = ctx.shadow_section
    summary = ctx.shadow

    total = sh.get("total_events")
    if total is None:
        total = summary.get("total_events", 0)

    events_path = PROJECT_ROOT / ARTIFACT_PATHS["shadow_events"]
    if not events_path.is_file() and total == 0:
        st.info("X.9 ledger ready; no runtime BUY events yet.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Events", total if total is not None else "NO_DATA")
    c2.metric("BUY_ALLOWED", sh.get("buy_allowed", summary.get("buy_allowed", 0)))
    c3.metric("BUY_BLOCKED_BY_TAE", sh.get("buy_blocked_by_tae", summary.get("buy_blocked_by_tae", 0)))
    c4.metric("BUY_SKIPPED_OTHER", sh.get("buy_skipped_other_reason", summary.get("buy_skipped_other_reason", 0)))

    c5, c6, c7 = st.columns(3)
    block_rate = sh.get("block_rate") if sh.get("block_rate") is not None else summary.get("block_rate")
    c5.metric("Block Rate", f"{block_rate:.1%}" if isinstance(block_rate, (int, float)) else "NO_DATA")
    c6.metric(
        "Outcome Tracking",
        sh.get("outcome_tracking_status") or summary.get("outcome_tracking_status", "NO_DATA"),
    )
    x9 = ctx.runtime.get("x9_readiness") or {}
    c7.metric("Ledger Wired", _fmt(x9.get("live_bot_wired", "NO_DATA")))

    latest = summary.get("latest_20_events") or []
    if latest:
        with st.expander("Latest shadow events", expanded=False):
            st.dataframe(pd.DataFrame(latest), width="stretch", hide_index=True)

    if events_path.is_file():
        try:
            events_df = pd.read_csv(events_path)
            with st.expander(f"Events CSV ({len(events_df)} rows)", expanded=False):
                st.dataframe(events_df.tail(30), width="stretch", hide_index=True)
        except Exception as exc:
            st.warning(f"Could not read events CSV: {exc}")


def render_strategy_lab(ctx: TAECommandCenterContext) -> None:
    st.subheader("🧠 Strategy Lab")
    strat = ctx.strategy
    counts = strat.get("counts") or {}
    counter = ctx.review.get("G_counterfactual_comparison") or {}
    groups = counter.get("groups") or {}

    c1, c2, c3 = st.columns(3)
    c1.metric("Robust Strategies", counts.get("robust_shortlist_count", "NO_DATA"))
    c2.metric("Weak Strategies", counts.get("weak_shortlist_count", "NO_DATA"))
    c3.metric("Registry Candidates", counts.get("registry_candidates_count", "NO_DATA"))

    for label in ("top_1", "top_5", "top_10"):
        grp = groups.get(label) or {}
        if not grp:
            continue
        status = grp.get("status", "NO_DATA")
        med_profit = grp.get("median_profit_pct")
        med_sharpe = grp.get("median_sharpe")
        st.markdown(
            f"**{label.replace('_', ' ').title()}** — status: `{status}` · "
            f"median profit%: {_fmt(med_profit)} · median Sharpe: {_fmt(med_sharpe)}"
        )
        ids = grp.get("strategy_ids") or []
        if ids:
            st.caption(", ".join(ids[:10]) + (" …" if len(ids) > 10 else ""))

    for label in ("top_100", "top_200"):
        grp = groups.get(label) or {}
        if grp.get("status") == "INSUFFICIENT_DATA":
            st.warning(
                f"{label}: INSUFFICIENT_DATA — only {grp.get('strategies_available', '?')} robust strategies available."
            )

    robust_list = strat.get("robust_shortlist_preview") or strat.get("robust_shortlist") or []
    if robust_list:
        with st.expander("Robust strategy preview", expanded=False):
            st.dataframe(pd.DataFrame(robust_list[:10]), width="stretch", hide_index=True)

    ranking_top = (ctx.review.get("H_learning_evidence_meta") or {}).get("strategy_ranking", {}).get("top") or []
    if ranking_top:
        with st.expander("Live strategy ranking (registry)", expanded=False):
            st.dataframe(pd.DataFrame(ranking_top), width="stretch", hide_index=True)


def render_execution_integrity(ctx: TAECommandCenterContext) -> None:
    st.subheader("🔎 Execution Integrity")
    exe = ctx.execution
    mor = ctx.mor
    recon = ctx.reconciliation.get("summary") or ctx.reconciliation

    protection = mor.get("sell_accounting_protection") or _detect_sell_accounting_protection(PROJECT_ROOT)
    if protection == "ACTIVE":
        st.success("Future SELL rows **protected** — `update_portfolio_prices()` skips SELL/DEPOSIT rows.")
    elif protection == "NOT_ACTIVE":
        st.error("SELL accounting protection NOT detected in live_bot.py")
    else:
        st.caption(f"SELL accounting protection: {protection}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", exe.get("status", recon.get("execution_integrity_status", "NO_DATA")))
    c2.metric("SELL Mismatches", exe.get("sell_mismatch_count", recon.get("sell_mismatched", "NO_DATA")))
    c3.metric("Corrected Realized", _fmt(exe.get("corrected_realized_pnl"), prefix="$"))
    c4.metric("Reported Realized", _fmt(exe.get("reported_realized_pnl"), prefix="$"))

    delta = exe.get("realized_pnl_delta")
    if delta is not None:
        st.metric("Realized PnL Delta (reported − corrected)", _fmt(delta, prefix="$"))

    biggest = exe.get("biggest_sell_mismatch") or ctx.financial.get("biggest_sell_mismatch")
    if biggest:
        st.markdown(
            f"**Biggest mismatch:** {biggest.get('ticker')} — reported {biggest.get('reported_pnl')} "
            f"vs expected {biggest.get('expected_realized_pnl')}"
        )

    root = exe.get("root_cause")
    if root:
        with st.expander("Root cause (historical)", expanded=False):
            st.write(root)

    st.caption(
        "Historical SELL rows in portfolio.csv remain mismatched in reconciliation reports; "
        "new SELL executions after the fix retain realized PnL."
    )


def render_project_book_panel(ctx: TAECommandCenterContext) -> None:
    st.subheader("📚 Project Book")
    ss = ctx.session_start
    pb = ctx.project_book

    c1, c2, c3 = st.columns(3)
    c1.metric("Last Completed Sprint", ss.get("last_completed_sprint", pb.get("latest_sprint", "NO_DATA")))
    c2.metric("Next Allowed Sprint", ss.get("next_allowed_sprint", "NO_DATA"))
    c3.metric("Mode", ss.get("mode", pb.get("governance_mode", "NO_DATA")))

    st.markdown(
        f"**Canonical runtime:** `{ss.get('canonical_runtime') or pb.get('canonical_runtime', 'live_bot.py')}`"
    )

    arch = pb.get("architecture_snippet")
    if arch:
        with st.expander("Current TAE architecture (from PROJECT_BOOK.md)", expanded=False):
            st.code(arch)

    with st.expander("SESSION_START.md", expanded=False):
        if ctx.session_start_text:
            st.markdown(ctx.session_start_text[:8000])
        else:
            st.caption("MISSING")

    with st.expander("PROJECT_BOOK.md (excerpt)", expanded=False):
        if ctx.project_book_text:
            st.markdown(ctx.project_book_text[:12000])
        else:
            st.caption("MISSING")


def render_artifact_status(ctx: TAECommandCenterContext) -> None:
    with st.expander("Artifact read status", expanded=False):
        rows = [{"artifact": k, "status": v} for k, v in sorted(ctx.artifact_status.items())]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def render_tae_command_center() -> None:
    """Main entry: render full TAE Command Center tab."""
    st.subheader("🏠 TAE Command Center")
    st.caption(
        "PAPER_ONLY · UI/OBSERVABILITY ONLY · Reads tae_full_ecosystem_review.json and related artifacts · "
        "No writes to portfolio.csv or live_signals.csv"
    )

    ctx = load_command_center_context()
    render_refresh_bar(ctx)
    st.divider()
    render_command_center_metrics(ctx)
    st.divider()

    render_financial_panel(ctx)
    st.divider()
    render_advisory_panel(ctx)
    st.divider()
    render_shadow_panel(ctx)
    st.divider()
    render_strategy_lab(ctx)
    st.divider()
    render_execution_integrity(ctx)
    st.divider()
    render_project_book_panel(ctx)
    render_artifact_status(ctx)

    if ctx.session_guard_tail:
        with st.expander("market_session_guard.log (tail)", expanded=False):
            st.code(ctx.session_guard_tail)
