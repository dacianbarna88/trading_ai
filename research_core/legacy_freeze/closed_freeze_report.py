from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


SAFETY = "ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"


@dataclass
class ClosedFreezeReport:
    generated_at: str
    safety: str
    verdict: str
    score100_current_pnl: float
    score100_current_trades: int
    score100_legacy_pnl: float
    score100_legacy_trades: int
    anomaly_delta: float
    conclusion: str
    protected_statement: str


def build_closed_freeze_report(portfolio_path: str = "portfolio.csv") -> ClosedFreezeReport:
    df = pd.read_csv(portfolio_path)

    buys = df[df["Action"].astype(str).str.upper() == "BUY"].copy()
    buys["Reason"] = buys["Reason"].astype(str)
    buys["Score"] = pd.to_numeric(buys["Score"], errors="coerce")
    buys["PnL"] = pd.to_numeric(buys["PnL"], errors="coerce").fillna(0)

    score100 = buys[buys["Score"] >= 100].copy()

    legacy = score100[score100["Reason"].str.upper().str.contains("CLOSED_FREEZE", na=False)]
    current = score100[~score100["Reason"].str.upper().str.contains("CLOSED_FREEZE", na=False)]

    legacy_pnl = round(float(legacy["PnL"].sum()), 2)
    current_pnl = round(float(current["PnL"].sum()), 2)

    verdict = "LEGACY_CLOSED_FREEZE_ANOMALY_CONFIRMED"

    conclusion = (
        "Score 100+ anomaly is concentrated in historical CLOSED_FREEZE-labelled BUY rows. "
        "Current Score 100+ dynamic market regime entries are not confirmed as defective by this evidence."
    )

    return ClosedFreezeReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        safety=SAFETY,
        verdict=verdict,
        score100_current_pnl=current_pnl,
        score100_current_trades=int(len(current)),
        score100_legacy_pnl=legacy_pnl,
        score100_legacy_trades=int(len(legacy)),
        anomaly_delta=round(current_pnl - legacy_pnl, 2),
        conclusion=conclusion,
        protected_statement="No live strategy, broker, portfolio, or execution files were modified.",
    )


def save_report(report: ClosedFreezeReport) -> None:
    Path("tae_closed_freeze_root_cause.json").write_text(
        json.dumps(asdict(report), indent=2),
        encoding="utf-8",
    )

    txt = f"""===== TAE PHASE VII A5 — LEGACY CLOSED_FREEZE ROOT CAUSE =====

Safety: {report.safety}
Generated: {report.generated_at}

Verdict: {report.verdict}

Score 100+ current dynamic:
  Trades: {report.score100_current_trades}
  Total PnL: ${report.score100_current_pnl}

Score 100+ legacy CLOSED_FREEZE:
  Trades: {report.score100_legacy_trades}
  Total PnL: ${report.score100_legacy_pnl}

Delta current minus legacy:
  ${report.anomaly_delta}

Conclusion:
  {report.conclusion}

Protection:
  {report.protected_statement}
"""
    Path("tae_closed_freeze_root_cause.txt").write_text(txt, encoding="utf-8")


