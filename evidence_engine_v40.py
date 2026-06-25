"""
Evidence Engine V4.0 — human-readable evidence dossiers for momentum signals.

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Decision-support research tool — not a trading executor or live bot.
Every score is derived from explicit, auditable rules.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.metrics.performance import compute_metrics

warnings.filterwarnings("ignore", category=FutureWarning)

SURVIVORS_CSV = "edge_discovery_survivors.csv"
ENSEMBLE_SCORES_CSV = "edge_ensemble_signal_scores.csv"
ENSEMBLE_BUCKETS_CSV = "edge_ensemble_bucket_stats.csv"
V18_FEATURES_CSV = "context_v18_signal_features.csv"

DOSSIERS_CSV = "evidence_signal_dossiers.csv"
LABEL_PERF_CSV = "evidence_label_performance.csv"
SUMMARY_TXT = "evidence_engine_summary.txt"

RETURN_COL = "Forward_Return_60d"

CONSENSUS_BUCKETS: list[tuple[str, float, float]] = [
    ("0-20", 0.0, 20.0),
    ("20-40", 20.0, 40.0),
    ("40-60", 40.0, 60.0),
    ("60-80", 60.0, 80.0),
    ("80-100", 80.0, 100.01),
]

OVERALL_WEIGHTS: dict[str, float] = {
    "edge_consensus": 0.35,
    "market_context": 0.20,
    "trend": 0.15,
    "volume": 0.10,
    "volatility": 0.10,
    "price_structure": 0.05,
    "risk": 0.05,
}

DECISION_THRESHOLDS: list[tuple[str, float, float]] = [
    ("IGNORE", 0.0, 40.0),
    ("WATCH", 40.0, 60.0),
    ("PAPER_CANDIDATE", 60.0, 80.0),
    ("HIGH_CONVICTION_PAPER_CANDIDATE", 80.0, 100.01),
]


def status_from_score(score: float) -> str:
    if score >= 75:
        return "STRONG_SUPPORT"
    if score >= 60:
        return "SUPPORT"
    if score >= 40:
        return "NEUTRAL"
    if score >= 25:
        return "WARNING"
    return "STRONG_WARNING"


def clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


@dataclass
class CategoryEvidence:
    score: float
    status: str
    explanation: str


@dataclass
class EvidenceConfig:
    survivors_path: Path = Path(SURVIVORS_CSV)
    ensemble_scores_path: Path = Path(ENSEMBLE_SCORES_CSV)
    ensemble_buckets_path: Path = Path(ENSEMBLE_BUCKETS_CSV)
    v18_features_path: Path = Path(V18_FEATURES_CSV)
    output_dir: Path = Path(".")
    min_high_conviction_trades: int = 100
    min_avg_lift_pct: float = 3.0
    min_win_lift_pct: float = 5.0
    conflict_penalty_max: float = 12.0


@dataclass
class BucketLookup:
    """Win rate and avg return by ensemble consensus bucket."""

    by_bucket: dict[str, dict[str, float]] = field(default_factory=dict)

    def consensus_bucket(self, score: float) -> str:
        for label, low, high in CONSENSUS_BUCKETS:
            if low <= score < high:
                return label
        return CONSENSUS_BUCKETS[-1][0]

    def expected_return(self, consensus_score: float) -> float | None:
        bucket = self.consensus_bucket(consensus_score)
        row = self.by_bucket.get(bucket)
        return row.get("Avg_Return") if row else None

    def win_probability(self, consensus_score: float) -> float | None:
        bucket = self.consensus_bucket(consensus_score)
        row = self.by_bucket.get(bucket)
        return row.get("Win_Rate") if row else None


class EvidenceDataLoader:
    """Load ensemble outputs and optional reference files."""

    def __init__(self, config: EvidenceConfig) -> None:
        self._config = config

    def load_signals(self) -> pd.DataFrame:
        path = self._config.ensemble_scores_path
        if not path.exists():
            raise FileNotFoundError(
                f"Required file missing: {path}. Run edge_ensemble_engine_v31.py first."
            )
        df = pd.read_csv(path)
        if RETURN_COL not in df.columns:
            raise ValueError(f"Signals file must contain {RETURN_COL}")
        df["Signal_Date"] = pd.to_datetime(df["Signal_Date"])
        df["Win"] = df["Win"].astype(bool) if "Win" in df.columns else (
            df[RETURN_COL].astype(float) > 0
        )
        return df

    def load_bucket_lookup(self) -> BucketLookup:
        path = self._config.ensemble_buckets_path
        lookup = BucketLookup()
        if not path.exists():
            return lookup
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            lookup.by_bucket[str(row["Bucket"])] = {
                "Trades": float(row.get("Trades", 0)),
                "Win_Rate": float(row.get("Win_Rate", 0)),
                "Avg_Return": float(row.get("Avg_Return", 0)),
                "Profit_Factor": float(row.get("Profit_Factor", 0)),
                "MAE_Median": float(row.get("MAE_Median", 0)),
            }
        return lookup

    def load_survivor_regime_bias(self) -> str:
        path = self._config.survivors_path
        if not path.exists():
            return "BEAR"
        df = pd.read_csv(path)
        bear_count = df["Rule_Description"].astype(str).str.contains("BEAR", case=False).sum()
        bull_count = df["Rule_Description"].astype(str).str.contains("BULL", case=False).sum()
        if bear_count >= bull_count:
            return "BEAR"
        return "BULL"


class MomentumEvidenceEvaluator:
    """Category 1 — initial momentum strength."""

    def evaluate(self, row: pd.Series) -> CategoryEvidence:
        gain = float(row.get("Daily_Gain_Pct", 0) or 0)
        if gain >= 15:
            score = 88.0
            detail = f"Large daily gain {gain:.1f}% indicates strong momentum impulse."
        elif gain >= 10:
            score = 78.0
            detail = f"Daily gain {gain:.1f}% is above typical continuation threshold."
        elif gain >= 7:
            score = 65.0
            detail = f"Daily gain {gain:.1f}% meets elevated momentum criteria."
        elif gain >= 5:
            score = 52.0
            detail = f"Daily gain {gain:.1f}% meets minimum 5% momentum filter."
        else:
            score = 30.0
            detail = f"Daily gain {gain:.1f}% is below standard momentum threshold."
        return CategoryEvidence(clamp_score(score), status_from_score(score), detail)


class MarketContextEvidenceEvaluator:
    """Category 2 — market regime and SPY context."""

    def __init__(self, favored_regime: str) -> None:
        self._favored = favored_regime

    def evaluate(self, row: pd.Series) -> CategoryEvidence:
        regime = str(row.get("Market_Regime", "NEUTRAL"))
        spy_vs = _safe_float(row.get("SPY_Close_vs_SMA200_Pct"))
        spy_60 = _safe_float(row.get("SPY_60d_Return_Pct"))

        if regime == self._favored:
            score = 92.0 if self._favored == "BEAR" else 75.0
            detail = (
                f"Signal occurred during {regime} regime where discovered edges "
                f"historically outperformed baseline."
            )
        elif regime == "NEUTRAL":
            score = 55.0
            detail = "Market regime is NEUTRAL — edge discovery showed mixed results here."
        else:
            score = 35.0
            detail = (
                f"Signal occurred during {regime} regime — survivor edges favor "
                f"{self._favored} conditions, not {regime}."
            )

        if spy_vs is not None and spy_vs < 0:
            score = min(100.0, score + 5.0)
            detail += " SPY is below its 200-day SMA."
        if spy_60 is not None and spy_60 < 0:
            detail += " SPY 60-day return is negative."

        score = clamp_score(score)
        return CategoryEvidence(score, status_from_score(score), detail.strip())


class TrendEvidenceEvaluator:
    """Category 3 — price vs moving averages."""

    def evaluate(self, row: pd.Series) -> CategoryEvidence:
        above_50 = _bool_val(row.get("Close_Above_SMA50"))
        above_200 = _bool_val(row.get("Close_Above_SMA200"))
        vs_50 = _safe_float(row.get("Close_vs_SMA50_Pct")) or _safe_float(row.get("Dist_SMA50_Pct"))
        vs_200 = _safe_float(row.get("Close_vs_SMA200_Pct")) or _safe_float(row.get("Dist_SMA200_Pct"))

        score = 55.0
        parts: list[str] = []

        if above_50 is False:
            score += 12.0
            parts.append("Price is below SMA50 — aligns with oversold continuation patterns.")
        elif above_50 is True:
            score += 5.0
            parts.append("Price is above SMA50 — momentum already extended.")

        if above_200 is False:
            score += 10.0
            parts.append("Price below SMA200 supports counter-trend bounce setups.")
        elif above_200 is True:
            parts.append("Price above SMA200 — trend already established.")

        if vs_50 is not None:
            parts.append(f"Distance to SMA50: {vs_50:.1f}%.")
        if vs_200 is not None:
            parts.append(f"Distance to SMA200: {vs_200:.1f}%.")

        if not parts:
            parts.append("Limited SMA context available for this signal.")

        score = clamp_score(score)
        return CategoryEvidence(score, status_from_score(score), " ".join(parts))


class VolumeEvidenceEvaluator:
    """Category 4 — participation and liquidity surge."""

    def evaluate(self, row: pd.Series) -> CategoryEvidence:
        vol = _safe_float(row.get("Volume_Ratio"))
        dvol = _safe_float(row.get("Dollar_Volume_Ratio")) or _safe_float(
            row.get("DollarVolume_Ratio")
        )

        score = 50.0
        parts: list[str] = []

        if vol is not None:
            if 1.5 <= vol <= 3.0:
                score += 25.0
                parts.append(f"Volume ratio {vol:.2f}x supports institutional participation.")
            elif vol > 3.0:
                score += 10.0
                parts.append(f"Volume ratio {vol:.2f}x is extreme — may include exhaustion risk.")
            elif vol >= 1.0:
                score += 12.0
                parts.append(f"Volume ratio {vol:.2f}x shows moderate participation.")
            else:
                score -= 10.0
                parts.append(f"Volume ratio {vol:.2f}x is thin — weaker confirmation.")

        if dvol is not None and dvol >= 2.0:
            score += 8.0
            parts.append(f"Dollar volume ratio {dvol:.2f}x confirms capital inflow.")

        if not parts:
            parts.append("Volume data unavailable.")

        score = clamp_score(score)
        return CategoryEvidence(score, status_from_score(score), " ".join(parts))


class VolatilityEvidenceEvaluator:
    """Category 5 — ATR and range expansion."""

    def evaluate(self, row: pd.Series) -> CategoryEvidence:
        atr = _safe_float(row.get("ATR_Pct")) or _safe_float(row.get("ATR_14_Pct"))
        range_pct = _safe_float(row.get("Range_Pct"))

        score = 60.0
        parts: list[str] = []

        if atr is not None:
            if atr < 2.0:
                score += 15.0
                parts.append(f"ATR {atr:.2f}% is low — controlled volatility environment.")
            elif atr <= 4.0:
                score += 5.0
                parts.append(f"ATR {atr:.2f}% is moderate — typical for momentum bursts.")
            else:
                score -= 20.0
                parts.append(f"ATR {atr:.2f}% is elevated — wider swings expected.")

        if range_pct is not None and range_pct >= 8.0:
            score -= 8.0
            parts.append(f"Daily range {range_pct:.1f}% is wide.")

        if not parts:
            parts.append("Volatility metrics unavailable.")

        score = clamp_score(score)
        return CategoryEvidence(score, status_from_score(score), " ".join(parts))


class PriceStructureEvidenceEvaluator:
    """Category 6 — gap, intraday behavior, close location."""

    def evaluate(self, row: pd.Series) -> CategoryEvidence:
        gap = _safe_float(row.get("Gap_Pct"))
        intraday = _safe_float(row.get("Intraday_Return_Pct"))
        location = _safe_float(row.get("Close_Location"))

        score = 55.0
        parts: list[str] = []

        if gap is not None:
            if gap >= 3.0:
                score += 12.0
                parts.append(f"Gap up {gap:.1f}% shows strong overnight demand.")
            elif gap >= 0:
                score += 5.0
                parts.append(f"Gap {gap:.1f}% is positive.")
            else:
                score -= 8.0
                parts.append(f"Gap down {gap:.1f}% — weaker opening structure.")

        if intraday is not None:
            if intraday > 0:
                score += 8.0
                parts.append(f"Intraday return +{intraday:.1f}% — buyers held control.")
            else:
                score -= 5.0
                parts.append(f"Intraday return {intraday:.1f}% — faded after open.")

        if location is not None:
            if location >= 0.66:
                score += 8.0
                parts.append(f"Close near high of range (location {location:.2f}).")
            elif location <= 0.33:
                score -= 8.0
                parts.append(f"Close near low of range (location {location:.2f}).")

        if not parts:
            parts.append("Price structure data limited.")

        score = clamp_score(score)
        return CategoryEvidence(score, status_from_score(score), " ".join(parts))


class RiskEvidenceEvaluator:
    """Category 7 — drawdown and tail risk (higher score = lower risk)."""

    def evaluate(self, row: pd.Series, bucket_lookup: BucketLookup) -> CategoryEvidence:
        atr = _safe_float(row.get("ATR_Pct")) or _safe_float(row.get("ATR_14_Pct"))
        mae = _safe_float(row.get("MAE"))
        consensus = _safe_float(row.get("Edge_Consensus_Score")) or 0.0
        bucket = bucket_lookup.consensus_bucket(consensus)
        bucket_mae = bucket_lookup.by_bucket.get(bucket, {}).get("MAE_Median")

        score = 65.0
        parts: list[str] = []

        if atr is not None and atr >= 4.0:
            score -= 20.0
            parts.append(f"ATR is elevated at {atr:.2f}% — larger adverse swings likely.")

        if mae is not None:
            if mae > -5.0:
                score += 10.0
                parts.append(f"Realized MAE {mae:.1f}% was shallow for this trade.")
            elif mae < -15.0:
                score -= 15.0
                parts.append(f"Realized MAE {mae:.1f}% indicates deep early drawdown.")

        if bucket_mae is not None:
            parts.append(
                f"Historical MAE median for consensus bucket {bucket}: {bucket_mae:.1f}%."
            )
            if bucket_mae < -10.0:
                score -= 10.0
                parts.append("Bucket suggests larger drawdown risk than baseline.")

        if not parts:
            parts.append("Risk metrics partially unavailable.")

        score = clamp_score(score)
        return CategoryEvidence(score, status_from_score(score), " ".join(parts))


class ConflictEvidenceEvaluator:
    """Category 8 — contradictory signals reduce confidence."""

    def __init__(self, favored_regime: str) -> None:
        self._favored = favored_regime

    def evaluate(self, row: pd.Series) -> CategoryEvidence:
        regime = str(row.get("Market_Regime", "NEUTRAL"))
        consensus = _safe_float(row.get("Edge_Consensus_Score")) or 0.0
        rsi = _safe_float(row.get("RSI_14")) or _safe_float(row.get("RSI14"))
        matching = int(row.get("Matching_Edge_Count", 0) or 0)

        score = 85.0
        conflicts: list[str] = []

        if consensus >= 60 and regime != self._favored and regime != "NEUTRAL":
            score -= 25.0
            conflicts.append(
                f"High edge consensus ({consensus:.0f}) conflicts with {regime} regime "
                f"(edges favor {self._favored})."
            )

        if rsi is not None and rsi > 70 and matching > 0:
            score -= 15.0
            conflicts.append(
                f"RSI {rsi:.1f} is overbought while oversold-edge rules matched."
            )

        if consensus >= 70 and (_safe_float(row.get("ATR_Pct")) or 0) > 4.5:
            score -= 10.0
            conflicts.append("High conviction score paired with very elevated ATR.")

        if matching == 0 and consensus > 40:
            score -= 12.0
            conflicts.append("Consensus score present but no survivor rules matched.")

        if not conflicts:
            explanation = "No major conflicts detected between context and discovered edges."
        else:
            explanation = "Conflicts: " + " ".join(conflicts)

        score = clamp_score(score)
        return CategoryEvidence(score, status_from_score(score), explanation)


class OverallEvidenceCalculator:
    """Weighted overall score with conflict penalty."""

    def __init__(self, config: EvidenceConfig) -> None:
        self._config = config

    def calculate(
        self,
        row: pd.Series,
        categories: dict[str, CategoryEvidence],
    ) -> tuple[float, float]:
        edge = _safe_float(row.get("Edge_Consensus_Score")) or categories.get(
            "edge_consensus_proxy", CategoryEvidence(0, "", "")
        ).score
        if "Edge_Consensus_Score" in row and not pd.isna(row["Edge_Consensus_Score"]):
            edge = float(row["Edge_Consensus_Score"])

        weighted = (
            edge * OVERALL_WEIGHTS["edge_consensus"]
            + categories["market_context"].score * OVERALL_WEIGHTS["market_context"]
            + categories["trend"].score * OVERALL_WEIGHTS["trend"]
            + categories["volume"].score * OVERALL_WEIGHTS["volume"]
            + categories["volatility"].score * OVERALL_WEIGHTS["volatility"]
            + categories["price_structure"].score * OVERALL_WEIGHTS["price_structure"]
            + categories["risk"].score * OVERALL_WEIGHTS["risk"]
        )

        conflict = categories["conflict"].score
        penalty = 0.0
        if conflict < 50:
            penalty = min(
                self._config.conflict_penalty_max,
                (50.0 - conflict) * 0.25,
            )
        overall = clamp_score(weighted - penalty)
        return overall, penalty


class DecisionEngine:
    """Map overall score to research decision labels."""

    def label(self, overall_score: float) -> str:
        for label, low, high in DECISION_THRESHOLDS:
            if low <= overall_score < high:
                return label
        return DECISION_THRESHOLDS[-1][0]

    def risk_level(self, risk_score: float, mae: float | None) -> str:
        if risk_score < 40 or (mae is not None and mae < -20.0):
            return "HIGH"
        if risk_score < 60:
            return "MEDIUM"
        return "LOW"


class DossierBuilder:
    """Build per-signal evidence dossiers."""

    def __init__(self, config: EvidenceConfig, bucket_lookup: BucketLookup, favored_regime: str) -> None:
        self._config = config
        self._bucket_lookup = bucket_lookup
        self._momentum = MomentumEvidenceEvaluator()
        self._market = MarketContextEvidenceEvaluator(favored_regime)
        self._trend = TrendEvidenceEvaluator()
        self._volume = VolumeEvidenceEvaluator()
        self._volatility = VolatilityEvidenceEvaluator()
        self._price_structure = PriceStructureEvidenceEvaluator()
        self._risk = RiskEvidenceEvaluator()
        self._conflict = ConflictEvidenceEvaluator(favored_regime)
        self._overall = OverallEvidenceCalculator(config)
        self._decision = DecisionEngine()

    def build(self, signals: pd.DataFrame) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for _, row in signals.iterrows():
            cats = {
                "momentum": self._momentum.evaluate(row),
                "market_context": self._market.evaluate(row),
                "trend": self._trend.evaluate(row),
                "volume": self._volume.evaluate(row),
                "volatility": self._volatility.evaluate(row),
                "price_structure": self._price_structure.evaluate(row),
                "risk": self._risk.evaluate(row, self._bucket_lookup),
                "conflict": self._conflict.evaluate(row),
            }
            overall, penalty = self._overall.calculate(row, cats)
            consensus = _safe_float(row.get("Edge_Consensus_Score")) or 0.0
            prob = self._bucket_lookup.win_probability(consensus)
            exp_ret = self._bucket_lookup.expected_return(consensus)
            mae = _safe_float(row.get("MAE"))

            dossier: dict[str, Any] = {
                "Ticker": row.get("Ticker"),
                "Signal_Date": row.get("Signal_Date"),
                f"{RETURN_COL}": row.get(RETURN_COL),
                "Win": bool(row.get("Win")),
                "Edge_Consensus_Score": consensus,
                "Matching_Edge_Count": int(row.get("Matching_Edge_Count", 0) or 0),
                "Matching_Family_Count": int(row.get("Matching_Family_Count", 0) or 0),
                "Matching_Rules_Sample": row.get("Matching_Rules_Sample", ""),
                "Momentum_Evidence_Score": cats["momentum"].score,
                "Momentum_Evidence_Status": cats["momentum"].status,
                "Momentum_Explanation": cats["momentum"].explanation,
                "Market_Context_Evidence_Score": cats["market_context"].score,
                "Market_Context_Evidence_Status": cats["market_context"].status,
                "Market_Context_Explanation": cats["market_context"].explanation,
                "Trend_Evidence_Score": cats["trend"].score,
                "Trend_Evidence_Status": cats["trend"].status,
                "Trend_Explanation": cats["trend"].explanation,
                "Volume_Evidence_Score": cats["volume"].score,
                "Volume_Evidence_Status": cats["volume"].status,
                "Volume_Explanation": cats["volume"].explanation,
                "Volatility_Evidence_Score": cats["volatility"].score,
                "Volatility_Evidence_Status": cats["volatility"].status,
                "Volatility_Explanation": cats["volatility"].explanation,
                "Price_Structure_Evidence_Score": cats["price_structure"].score,
                "Price_Structure_Evidence_Status": cats["price_structure"].status,
                "Price_Structure_Explanation": cats["price_structure"].explanation,
                "Risk_Evidence_Score": cats["risk"].score,
                "Risk_Evidence_Status": cats["risk"].status,
                "Risk_Explanation": cats["risk"].explanation,
                "Conflict_Evidence_Score": cats["conflict"].score,
                "Conflict_Evidence_Status": cats["conflict"].status,
                "Conflict_Explanation": cats["conflict"].explanation,
                "Conflict_Penalty_Applied": round(penalty, 2),
                "Overall_Evidence_Score": overall,
                "Estimated_Probability_Positive": round(prob, 2) if prob is not None else None,
                "Expected_Return_Bucket": round(exp_ret, 4) if exp_ret is not None else None,
                "Risk_Level": self._decision.risk_level(cats["risk"].score, mae),
                "Decision_Label": self._decision.label(overall),
            }
            rows.append(dossier)
        return pd.DataFrame(rows)


class LabelBacktester:
    """Performance stats per decision label."""

    def __init__(self, baseline: dict[str, Any]) -> None:
        self._baseline = baseline

    def run(self, dossiers: pd.DataFrame) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for label in [t[0] for t in DECISION_THRESHOLDS]:
            sub = dossiers[dossiers["Decision_Label"] == label]
            rets = sub[RETURN_COL].astype(float).values
            metrics = compute_metrics(rets, self._baseline)
            metrics["Decision_Label"] = label
            metrics["MAE_Median"] = (
                round(float(sub["MAE"].median()), 4)
                if "MAE" in sub.columns and len(sub)
                else None
            )
            metrics["MFE_Median"] = (
                round(float(sub["MFE"].median()), 4)
                if "MFE" in sub.columns and len(sub)
                else None
            )
            rows.append(metrics)
        return pd.DataFrame(rows)


class VerdictEngine:
    """Final evidence engine research verdict."""

    def decide(
        self,
        baseline: dict[str, Any],
        label_perf: pd.DataFrame,
        correlation: float,
    ) -> tuple[str, str]:
        high = label_perf[label_perf["Decision_Label"] == "HIGH_CONVICTION_PAPER_CANDIDATE"]
        if high.empty or int(high.iloc[0]["Trades"]) == 0:
            return "EVIDENCE_ENGINE_WEAK", "No HIGH_CONVICTION_PAPER_CANDIDATE trades."

        h = high.iloc[0]
        confirmed = (
            int(h["Trades"]) >= 100
            and float(h["Avg_Return"]) > float(baseline["Avg_Return"]) + 3.0
            and float(h["Win_Rate"]) > float(baseline["Win_Rate"]) + 5.0
            and float(h["Profit_Factor"]) > float(baseline["Profit_Factor"])
        )
        partial = (
            int(h["Trades"]) >= 50
            and float(h["Avg_Return"]) > float(baseline["Avg_Return"])
            and correlation > 0.03
        )
        detail = (
            f"HIGH_CONVICTION trades={int(h['Trades'])} avg={h['Avg_Return']}% "
            f"win={h['Win_Rate']}% pf={h['Profit_Factor']} corr={round(correlation, 4)}"
        )
        if confirmed:
            return "EVIDENCE_ENGINE_CONFIRMED", detail
        if partial:
            return "EVIDENCE_ENGINE_PARTIAL", detail
        return "EVIDENCE_ENGINE_WEAK", detail


class EvidenceReporter:
    """Write CSV outputs and summary."""

    def __init__(self, config: EvidenceConfig) -> None:
        self._config = config

    def write(
        self,
        dossiers: pd.DataFrame,
        label_perf: pd.DataFrame,
        baseline: dict[str, Any],
        correlation: float,
        verdict: str,
        verdict_detail: str,
    ) -> str:
        out_dir = self._config.output_dir
        dossiers_path = out_dir / DOSSIERS_CSV
        label_path = out_dir / LABEL_PERF_CSV
        summary_path = out_dir / SUMMARY_TXT

        dossiers.to_csv(dossiers_path, index=False)
        label_perf.to_csv(label_path, index=False)

        top_evidence = dossiers.nlargest(20, "Overall_Evidence_Score")
        top_warnings = dossiers.nsmallest(20, "Overall_Evidence_Score")

        lines = [
            "===== EVIDENCE ENGINE V4.0 =====",
            "",
            RESEARCH_SAFETY_BANNER,
            "Decision-support research — not execution, not live trading.",
            "",
            f"Total signals analyzed: {len(dossiers)}",
            "",
            "--- Baseline (all signals) ---",
            f"  Trades: {baseline['Trades']}",
            f"  Win_Rate: {baseline['Win_Rate']}%",
            f"  Avg_Return: {baseline['Avg_Return']}%",
            f"  Profit_Factor: {baseline['Profit_Factor']}",
            "",
            "--- Decision label performance ---",
        ]
        for _, row in label_perf.iterrows():
            lines.append(
                f"  {row['Decision_Label']}: trades={int(row['Trades'])} "
                f"win={row['Win_Rate']}% avg={row['Avg_Return']}% pf={row['Profit_Factor']}"
            )
        lines.extend(
            [
                "",
                "--- Score vs return ---",
                f"Correlation (Overall_Evidence_Score vs {RETURN_COL}): {round(correlation, 4)}",
                "Higher evidence score improves returns: "
                + ("YES" if correlation > 0.05 else "WEAK / NO"),
                "",
                "--- Top 20 strongest evidence signals ---",
            ]
        )
        for _, r in top_evidence.iterrows():
            lines.append(
                f"  {r['Ticker']} {r['Signal_Date']} score={r['Overall_Evidence_Score']} "
                f"label={r['Decision_Label']} ret={r[RETURN_COL]}"
            )
        lines.extend(["", "--- Top 20 strongest warnings (lowest scores) ---"])
        for _, r in top_warnings.iterrows():
            lines.append(
                f"  {r['Ticker']} {r['Signal_Date']} score={r['Overall_Evidence_Score']} "
                f"label={r['Decision_Label']} conflict={r['Conflict_Evidence_Status']}"
            )
        lines.extend(
            [
                "",
                f"FINAL VERDICT: {verdict}",
                verdict_detail,
                "",
                f"Saved: {dossiers_path}",
                f"Saved: {label_path}",
                f"Saved: {summary_path}",
                "",
            ]
        )
        summary = "\n".join(lines)
        summary_path.write_text(summary, encoding="utf-8")
        print(summary)
        return summary


class EvidenceEngine:
    """Orchestrates V4.0 evidence dossier generation."""

    def __init__(self, config: EvidenceConfig | None = None) -> None:
        self.config = config or EvidenceConfig()

    def run(self) -> dict[str, Any]:
        print("===== EVIDENCE ENGINE V4.0 =====")
        print(RESEARCH_SAFETY_BANNER)
        print()

        loader = EvidenceDataLoader(self.config)
        signals = loader.load_signals()
        bucket_lookup = loader.load_bucket_lookup()
        favored_regime = loader.load_survivor_regime_bias()
        print(f"Loaded {len(signals)} signals. Favored regime bias: {favored_regime}.")

        baseline_rets = signals[RETURN_COL].astype(float).values
        baseline = compute_metrics(baseline_rets, {"Avg_Return": 0, "Win_Rate": 0})

        builder = DossierBuilder(self.config, bucket_lookup, favored_regime)
        dossiers = builder.build(signals)

        # Label performance with MAE/MFE from signals
        merged = dossiers.merge(
            signals[["Ticker", "Signal_Date", "MAE", "MFE"]],
            on=["Ticker", "Signal_Date"],
            how="left",
        )
        label_perf = LabelBacktester(baseline).run(merged)

        valid = dossiers[["Overall_Evidence_Score", RETURN_COL]].dropna()
        correlation = (
            float(valid["Overall_Evidence_Score"].corr(valid[RETURN_COL]))
            if len(valid) > 2
            else 0.0
        )

        verdict, verdict_detail = VerdictEngine().decide(baseline, label_perf, correlation)

        EvidenceReporter(self.config).write(
            dossiers=dossiers,
            label_perf=label_perf,
            baseline=baseline,
            correlation=correlation,
            verdict=verdict,
            verdict_detail=verdict_detail,
        )

        return {
            "status": "ok",
            "signals": len(dossiers),
            "verdict": verdict,
            "correlation": correlation,
        }


def _safe_float(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_val(value: Any) -> bool | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if pd.isna(value):
        return None
    return bool(value)


def main() -> None:
    EvidenceEngine().run()


if __name__ == "__main__":
    main()
