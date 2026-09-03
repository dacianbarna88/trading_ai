"""
V5.1 Policy Shadow Report — summarizes core/v51_policy_shadow.py's raw
observation log into a decision-support report.

PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE | READ_ONLY

Reads v51_policy_shadow_events.csv (written by live_bot.py every cycle)
and reports how often, and on what, live_bot.py's static policy and
live_bot_v5_1.py's dynamic policy would have decided differently — the
evidence base for the Level 1 migration decision. Never touches
portfolio.csv or the events file itself.
"""

from collections import Counter
from pathlib import Path

import pandas as pd

EVENTS_FILE = "v51_policy_shadow_events.csv"
SUMMARY_FILE = "v51_policy_shadow_report_summary.txt"

CHECK_REGIME = "REGIME"
CHECK_MAX_POSITIONS = "MAX_POSITIONS"
CHECK_ENTRY_THRESHOLD = "ENTRY_THRESHOLD"
CHECK_EXIT_STRATEGY = "EXIT_STRATEGY"


def _pct(part: int, whole: int) -> str:
    if whole <= 0:
        return "n/a"
    return f"{(part / whole) * 100:.1f}%"


def build_report(df: pd.DataFrame) -> str:
    lines = ["===== V5.1 POLICY SHADOW REPORT =====", ""]

    # REGIME and MAX_POSITIONS are logged every cycle (agree or not), so
    # the REGIME row count is the true number of cycles observed.
    regime_rows = df[df["check_type"] == CHECK_REGIME]
    cycles_observed = len(regime_rows)
    lines.append(f"Cycles observed: {cycles_observed}")
    lines.append("")

    if cycles_observed == 0:
        lines.append("No shadow data yet — live_bot.py needs to run at least one cycle.")
        return "\n".join(lines)

    # pandas infers the CSV "agree" column as bool dtype (it recognizes
    # lowercase true/false), so normalize to a lowercase string before
    # comparing rather than assuming either dtype.
    agree_lower = df["agree"].astype(str).str.lower()

    # --- Regime ---
    regime_disagree = regime_rows[agree_lower.loc[regime_rows.index] == "false"]
    lines.append(
        f"Regime divergence: {len(regime_disagree)}/{cycles_observed} cycles "
        f"({_pct(len(regime_disagree), cycles_observed)})"
    )
    if not regime_disagree.empty:
        dynamic_dist = Counter(regime_disagree["dynamic_value"])
        for value, count in dynamic_dist.most_common():
            lines.append(f"  dynamic regime was {value} while live disagreed: {count} cycle(s)")
    lines.append("")

    # --- Max positions ---
    cap_rows = df[df["check_type"] == CHECK_MAX_POSITIONS]
    cap_disagree = cap_rows[agree_lower.loc[cap_rows.index] == "false"]
    lines.append(
        f"MAX_POSITIONS block/allow divergence: {len(cap_disagree)}/{len(cap_rows)} cycles "
        f"({_pct(len(cap_disagree), len(cap_rows))})"
    )
    lines.append("")

    # --- Entry threshold: only divergences are ever logged. ---
    entry_rows = df[df["check_type"] == CHECK_ENTRY_THRESHOLD]
    lines.append(
        f"Entry-threshold divergences logged: {len(entry_rows)} "
        f"(across {cycles_observed} cycles observed; only divergent candidates are logged)"
    )
    if not entry_rows.empty:
        by_ticker = Counter(entry_rows["ticker"])
        for ticker, count in by_ticker.most_common(10):
            lines.append(f"  {ticker}: {count} time(s)")
    lines.append("")

    # --- Exit strategy: only divergences are ever logged. ---
    exit_rows = df[df["check_type"] == CHECK_EXIT_STRATEGY]
    trailing_would_exit = exit_rows[exit_rows["dynamic_value"].str.contains("EXIT", na=False)]
    fixed_would_exit = exit_rows[exit_rows["live_value"].str.contains("EXIT", na=False)]
    lines.append(f"Exit-strategy divergences logged: {len(exit_rows)}")
    lines.append(f"  trailing-stop would exit while fixed TP/SL holds: {len(trailing_would_exit)}")
    lines.append(f"  fixed TP/SL would exit while trailing-stop holds: {len(fixed_would_exit)}")
    if not exit_rows.empty:
        by_ticker = Counter(exit_rows["ticker"])
        for ticker, count in by_ticker.most_common(10):
            lines.append(f"  {ticker}: {count} time(s)")
    lines.append("")

    lines.append("Status:")
    lines.append("PAPER_ONLY | NO_BROKER | NO_EXECUTION | READ_ONLY")

    return "\n".join(lines)


def main() -> int:
    events_path = Path(EVENTS_FILE)

    if not events_path.is_file():
        summary = (
            "===== V5.1 POLICY SHADOW REPORT =====\n\n"
            "No shadow data yet — live_bot.py needs to run at least one cycle "
            "with V51_POLICY_SHADOW_MODE enabled."
        )
        print(summary)
        Path(SUMMARY_FILE).write_text(summary, encoding="utf-8")
        return 0

    df = pd.read_csv(events_path)
    summary = build_report(df)
    print(summary)
    Path(SUMMARY_FILE).write_text(summary, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
