from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


SAFETY = "ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"


@dataclass
class CohortStats:
    name: str
    trades: int
    total_pnl: float
    avg_pnl: float
    median_pnl: float
    win_rate: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    expectancy: float


@dataclass
class StatisticalAuditReport:
    generated_at: str
    safety: str
    verdict: str
    all_score100: CohortStats
    current_score100: CohortStats
    legacy_closed_freeze_score100: CohortStats
    delta_current_vs_legacy_total_pnl: float
    delta_current_vs_legacy_expectancy: float
    conclusion: str


def _stats(name: str, df: pd.DataFrame) -> CohortStats:
    pnl = pd.to_numeric(df["PnL"], errors="coerce").fillna(0)

    trades = int(len(pnl))
    total = round(float(pnl.sum()), 2)
    avg = round(float(pnl.mean()), 2) if trades else 0.0
    median = round(float(pnl.median()), 2) if trades else 0.0

    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]

    gross_profit = round(float(wins.sum()), 2)
    gross_loss = round(abs(float(losses.sum())), 2)

    win_rate = round(float((pnl > 0).mean() * 100), 2) if trades else 0.0
    profit_factor = round(gross_profit / gross_loss, 4) if gross_loss else 999.0 if gross_profit else 0.0
    expectancy = avg

    return CohortStats(
        name=name,
        trades=trades,
        total_pnl=total,
        avg_pnl=avg,
        median_pnl=median,
        win_rate=win_rate,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=profit_factor,
        expectancy=expectancy,
    )


def build_report(portfolio_path: str = "portfolio.csv") -> StatisticalAuditReport:
    df = pd.read_csv(portfolio_path)

    buys = df[df["Action"].astype(str).str.upper() == "BUY"].copy()
    buys["Reason"] = buys["Reason"].astype(str)
    buys["Score"] = pd.to_numeric(buys["Score"], errors="coerce")
    buys["PnL"] = pd.to_numeric(buys["PnL"], errors="coerce").fillna(0)

    score100 = buys[buys["Score"] >= 100].copy()

    legacy = score100[
        score100["Reason"].str.upper().str.contains("CLOSED_FREEZE", na=False)
    ].copy()

    current = score100[
        ~score100["Reason"].str.upper().str.contains("CLOSED_FREEZE", na=False)
    ].copy()

    all_stats = _stats("ALL_SCORE_100_PLUS", score100)
    current_stats = _stats("CURRENT_SCORE_100_PLUS", current)
    legacy_stats = _stats("LEGACY_CLOSED_FREEZE_SCORE_100_PLUS", legacy)

    delta_total = round(current_stats.total_pnl - legacy_stats.total_pnl, 2)
    delta_expectancy = round(current_stats.expectancy - legacy_stats.expectancy, 2)

    if current_stats.total_pnl > 0 and legacy_stats.total_pnl < 0:
        verdict = "LEGACY_CLOSED_FREEZE_DISTORTION_CONFIRMED"
        conclusion = (
            "The negative Score 100+ anomaly is statistically concentrated in legacy CLOSED_FREEZE rows. "
            "Removing that legacy cohort changes Score 100+ from distorted/negative to positive. "
            "Current Score 100+ logic is not proven defective by this dataset."
        )
    else:
        verdict = "INCONCLUSIVE"
        conclusion = (
            "The available data does not clearly isolate CLOSED_FREEZE as the distortion source."
        )

    return StatisticalAuditReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        safety=SAFETY,
        verdict=verdict,
        all_score100=all_stats,
        current_score100=current_stats,
        legacy_closed_freeze_score100=legacy_stats,
        delta_current_vs_legacy_total_pnl=delta_total,
        delta_current_vs_legacy_expectancy=delta_expectancy,
        conclusion=conclusion,
    )


def save_report(report: StatisticalAuditReport) -> None:
    Path("tae_closed_freeze_statistical_audit.json").write_text(
        json.dumps(asdict(report), indent=2),
        encoding="utf-8",
    )

    def block(s: CohortStats) -> str:
        return f"""
{s.name}
  Trades: {s.trades}
  Total PnL: ${s.total_pnl}
  Avg PnL / Expectancy: ${s.expectancy}
  Median PnL: ${s.median_pnl}
  Win rate: {s.win_rate}%
  Gross profit: ${s.gross_profit}
  Gross loss: ${s.gross_loss}
  Profit factor: {s.profit_factor}
"""

    txt = f"""===== TAE PHASE VII A6 — CLOSED_FREEZE STATISTICAL VALIDATION AUDIT =====

Safety: {report.safety}
Generated: {report.generated_at}

Verdict: {report.verdict}

{block(report.all_score100)}
{block(report.current_score100)}
{block(report.legacy_closed_freeze_score100)}

Delta current vs legacy total PnL:
  ${report.delta_current_vs_legacy_total_pnl}

Delta current vs legacy expectancy:
  ${report.delta_current_vs_legacy_expectancy}

Conclusion:
  {report.conclusion}

Protection:
  ANALYSIS ONLY — no live strategy, broker, portfolio, or execution files were modified.
"""
    Path("tae_closed_freeze_statistical_audit.txt").write_text(txt, encoding="utf-8")
