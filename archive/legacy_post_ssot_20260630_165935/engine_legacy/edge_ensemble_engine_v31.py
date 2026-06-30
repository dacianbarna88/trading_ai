"""
Edge Ensemble Engine V3.1 — consensus scoring over V3.0 survivor edges.

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Combines surviving discovered edges into an Edge Consensus Score per signal.
Not production trading — research validation only.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.features.registry import FeatureBinRegistry
from research_core.metrics.performance import compute_metrics
from research_core.services.dataset_builder import SignalDatasetBuilder
from research_core.types import Rule
from research_core.config import DiscoveryConfig

warnings.filterwarnings("ignore", category=FutureWarning)

SURVIVORS_CSV = "edge_discovery_survivors.csv"
CANDIDATES_CSV = "edge_discovery_candidates.csv"
V18_FEATURES_CSV = "context_v18_signal_features.csv"

SIGNAL_SCORES_CSV = "edge_ensemble_signal_scores.csv"
BUCKET_STATS_CSV = "edge_ensemble_bucket_stats.csv"
SUMMARY_TXT = "edge_ensemble_summary.txt"

RETURN_COL = "Forward_Return_60d"
BUCKETS: list[tuple[str, float, float]] = [
    ("0-20", 0.0, 20.0),
    ("20-40", 20.0, 40.0),
    ("40-60", 40.0, 60.0),
    ("60-80", 60.0, 80.0),
    ("80-100", 80.0, 100.01),
]

FAMILY_KEYWORDS: dict[str, list[str]] = {
    "Market Regime": ["Regime_", "SPY_Above", "SPY_Below"],
    "Trend": ["SMA", "Dist_SMA", "Close_Above"],
    "RSI": ["RSI"],
    "Volatility": ["ATR"],
    "Volume": ["Volume", "Dollar_Volume", "DollarVolume"],
    "Price Structure": ["Gap_", "Intraday", "Range_", "Body_", "Wick_", "Close_Location"],
}


@dataclass
class EnsembleConfig:
    survivors_path: Path = Path(SURVIVORS_CSV)
    v18_features_path: Path = Path(V18_FEATURES_CSV)
    candidates_path: Path = Path(CANDIDATES_CSV)
    output_dir: Path = Path(".")
    min_top_bucket_trades: int = 100
    min_avg_lift_pct: float = 3.0
    min_win_lift_pct: float = 5.0
    family_duplicate_weight: float = 0.25
    max_theoretical_score: float | None = None


@dataclass
class SurvivorEdge:
    rule_id: str
    description: str
    rule: Rule
    family: str
    weight: float
    bin_columns: tuple[str, ...]
    metrics: dict[str, Any] = field(default_factory=dict)


class RuleIdParser:
    """Parse V3.0 Rule_ID strings into BIN column names."""

    @staticmethod
    def parse_bin_columns(rule_id: str) -> tuple[str, ...]:
        rid = rule_id.strip()
        if rid.startswith("T_"):
            rid = rid[2:]
        if rid.startswith("P_"):
            rid = rid[2:]

        if "_S_BIN_" not in rid:
            if rid.startswith("S_"):
                return (rid[2:],)
            if rid.startswith("BIN_"):
                return (rid,)
            return (rid,)

        parts = rid.split("_S_BIN_")
        bins: list[str] = []
        first = parts[0]
        if first.startswith("S_"):
            first = first[2:]
        bins.append(first)
        for part in parts[1:]:
            bins.append(part if part.startswith("BIN_") else f"BIN_{part}")
        return tuple(bins)


class EdgeFamilyClassifier:
    """Assign survivor edges to auditable families."""

    @staticmethod
    def classify(rule_id: str, description: str, bin_columns: tuple[str, ...]) -> str:
        text = f"{rule_id} {description} " + " ".join(bin_columns)
        if "BIN_Sector_" in text:
            return "Mixed"
        scores: dict[str, int] = {}
        for family, keywords in FAMILY_KEYWORDS.items():
            scores[family] = sum(1 for keyword in keywords if keyword in text)
        positive = {f: s for f, s in scores.items() if s > 0}
        if not positive:
            return "Mixed"
        best_score = max(positive.values())
        winners = [f for f, s in positive.items() if s == best_score]
        return winners[0] if len(winners) == 1 else "Mixed"


class SurvivorLoader:
    """Load and parse V3.0 survivor edges."""

    def __init__(self, config: EnsembleConfig) -> None:
        self._config = config

    def load(self) -> list[SurvivorEdge]:
        path = self._config.survivors_path
        if not path.exists():
            raise FileNotFoundError(f"Survivors file not found: {path}")

        df = pd.read_csv(path)
        edges: list[SurvivorEdge] = []
        for _, row in df.iterrows():
            rule_id = str(row["Rule_ID"])
            description = str(row["Rule_Description"])
            bins = RuleIdParser.parse_bin_columns(rule_id)
            family = EdgeFamilyClassifier.classify(rule_id, description, bins)
            weight = self._edge_weight(row)
            feature_groups = frozenset({family})
            rule = Rule(
                rule_id=rule_id,
                description=description,
                bin_columns=bins,
                complexity=int(row.get("Complexity", len(bins))),
                feature_groups=feature_groups,
            )
            edges.append(
                SurvivorEdge(
                    rule_id=rule_id,
                    description=description,
                    rule=rule,
                    family=family,
                    weight=weight,
                    bin_columns=bins,
                    metrics=row.to_dict(),
                )
            )
        return edges

    def _edge_weight(self, row: pd.Series) -> float:
        trades = float(row.get("Trades", 0))
        sector_div = float(row.get("Sector_Diversity", 0))
        ticker_div = float(row.get("Ticker_Diversity", 0))
        pf = float(row.get("Profit_Factor", 0))
        trades_score = min(trades / 300.0, 1.0) * 100.0
        diversity_score = (
            min(sector_div / 6.0, 1.0) + min(ticker_div / 150.0, 1.0)
        ) / 2.0 * 100.0
        pf_score = min(pf / 8.0, 1.0) * 100.0
        return (
            float(row.get("Edge_Confidence_Score", 0)) * 0.35
            + float(row.get("Robustness_Score", 0)) * 0.20
            + float(row.get("Walk_Forward_Score", 0)) * 0.20
            + trades_score * 0.10
            + pf_score * 0.10
            + diversity_score * 0.05
        )


class SignalFrameLoader:
    """Load momentum signals and apply V3.0-compatible feature bins."""

    def __init__(self, config: EnsembleConfig) -> None:
        self._config = config
        self._registry = FeatureBinRegistry()

    def load(self, required_bins: set[str]) -> pd.DataFrame:
        path = self._config.v18_features_path
        if path.exists():
            raw = pd.read_csv(path)
            frame = self._normalize_v18(raw)
        else:
            print(f"Note: {path} not found — building signals via research_core.")
            frame = self._build_from_research_core()

        if self._needs_sma_enrichment(frame, required_bins):
            frame = self._enrich_missing_sma(frame)

        self._registry.register_defaults()
        binned = self._registry.apply(frame)
        if RETURN_COL not in binned.columns and "Return_60d" in binned.columns:
            binned[RETURN_COL] = binned["Return_60d"]
        return binned

    def _normalize_v18(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        if "Signal_Date" in out.columns:
            out["Signal_Date"] = pd.to_datetime(out["Signal_Date"])
        out["RSI14"] = pd.to_numeric(out.get("RSI_14"), errors="coerce")
        out["ATR_Pct"] = pd.to_numeric(out.get("ATR_14_Pct"), errors="coerce")
        out["Dist_SMA200_Pct"] = pd.to_numeric(out.get("Close_vs_SMA200_Pct"), errors="coerce")
        out["Dist_SMA50_Pct"] = pd.to_numeric(out.get("Close_vs_SMA50_Pct"), errors="coerce")
        out["Dist_SMA20_Pct"] = pd.to_numeric(out.get("Close_vs_SMA20_Pct"), errors="coerce")
        out["Dist_SMA100_Pct"] = pd.to_numeric(out.get("Close_vs_SMA100_Pct"), errors="coerce")
        out["Dollar_Volume_Ratio"] = pd.to_numeric(
            out.get("DollarVolume_Ratio"), errors="coerce"
        )
        out["Volume_Ratio"] = pd.to_numeric(out.get("Volume_Ratio"), errors="coerce")
        out["Gap_Pct"] = pd.to_numeric(out.get("Gap_Pct"), errors="coerce")
        out["Intraday_Return_Pct"] = pd.to_numeric(out.get("Intraday_Return_Pct"), errors="coerce")
        out["Range_Pct"] = pd.to_numeric(out.get("Range_Pct"), errors="coerce")
        out["Close_Location"] = pd.to_numeric(out.get("Close_Location"), errors="coerce")
        out[RETURN_COL] = pd.to_numeric(out.get(RETURN_COL), errors="coerce")
        out["MAE"] = pd.to_numeric(out.get("MAE"), errors="coerce")
        out["MFE"] = pd.to_numeric(out.get("MFE"), errors="coerce")

        if "Sector" not in out.columns:
            sector_map = DiscoveryConfig.v30_default().sector_map()
            out["Sector"] = out["Ticker"].astype(str).str.upper().map(sector_map).fillna("Other")

        self._set_trend_flags_from_pct(out)
        return out

    def _set_trend_flags_from_pct(self, out: pd.DataFrame) -> None:
        if "Close_vs_SMA50_Pct" in out.columns:
            pct = pd.to_numeric(out["Close_vs_SMA50_Pct"], errors="coerce")
            out["Close_Above_SMA50"] = pct > 0
        if "Close_vs_SMA200_Pct" in out.columns:
            pct = pd.to_numeric(out["Close_vs_SMA200_Pct"], errors="coerce")
            out["Close_Above_SMA200"] = pct > 0
        if "SPY_Close_vs_SMA200_Pct" in out.columns:
            pct = pd.to_numeric(out["SPY_Close_vs_SMA200_Pct"], errors="coerce")
            out["SPY_Above_SMA200"] = pct > 0
        if "Close_vs_SMA20_Pct" in out.columns:
            pct = pd.to_numeric(out["Close_vs_SMA20_Pct"], errors="coerce")
            out["Close_Above_SMA20"] = pct.notna() & (pct > 0)
        if "Close_vs_SMA100_Pct" in out.columns:
            pct = pd.to_numeric(out["Close_vs_SMA100_Pct"], errors="coerce")
            out["Close_Above_SMA100"] = pct.notna() & (pct > 0)

    def _build_from_research_core(self) -> pd.DataFrame:
        builder = SignalDatasetBuilder(DiscoveryConfig.v30_default())
        dataset = builder.build()
        if dataset is None:
            raise RuntimeError("Failed to build signal dataset from research_core.")
        out = dataset.signals.copy()
        out[RETURN_COL] = out["Return_60d"]
        return out

    def _needs_sma_enrichment(self, frame: pd.DataFrame, required_bins: set[str]) -> bool:
        need_20 = any("SMA20" in b for b in required_bins)
        need_100 = any("SMA100" in b for b in required_bins)
        if not need_20 and not need_100:
            return False
        if need_20 and "Close_Above_SMA20" not in frame.columns:
            return True
        if need_100 and "Close_Above_SMA100" not in frame.columns:
            return True
        if need_20 and "Close_Above_SMA20" in frame.columns and frame["Close_Above_SMA20"].isna().all():
            return True
        if need_100 and "Close_Above_SMA100" in frame.columns and frame["Close_Above_SMA100"].isna().all():
            return True
        return False

    def _enrich_missing_sma(self, frame: pd.DataFrame) -> pd.DataFrame:
        from research_core.services.market_data import MarketDataService

        service = MarketDataService(DiscoveryConfig.v30_default())
        out = frame.copy()
        if "Close_Above_SMA20" not in out.columns:
            out["Close_Above_SMA20"] = pd.Series(pd.NA, index=out.index)
        if "Close_Above_SMA100" not in out.columns:
            out["Close_Above_SMA100"] = pd.Series(pd.NA, index=out.index)

        tickers = out["Ticker"].astype(str).str.upper().unique()
        print(f"Enriching SMA20/SMA100 flags for {len(tickers)} tickers...")
        for ticker in tickers:
            raw = service.download(ticker)
            if raw.empty:
                continue
            enriched = service.enrich_ticker(raw)
            mask = out["Ticker"].astype(str).str.upper() == ticker
            dates = pd.to_datetime(out.loc[mask, "Signal_Date"])
            for idx, signal_date in zip(out.index[mask], dates):
                if signal_date not in enriched.index:
                    continue
                row = enriched.loc[signal_date]
                if pd.notna(row.get("Close_Above_SMA20")):
                    out.at[idx, "Close_Above_SMA20"] = bool(row["Close_Above_SMA20"])
                if pd.notna(row.get("Close_Above_SMA100")):
                    out.at[idx, "Close_Above_SMA100"] = bool(row["Close_Above_SMA100"])
        return out


class ConsensusScorer:
    """Compute raw votes, family diversification, and Edge_Consensus_Score."""

    def __init__(self, config: EnsembleConfig, edges: list[SurvivorEdge]) -> None:
        self._config = config
        self._edges = self._filter_applicable(edges)

    def _filter_applicable(self, edges: list[SurvivorEdge]) -> list[SurvivorEdge]:
        applicable: list[SurvivorEdge] = []
        for edge in edges:
            applicable.append(edge)
        return applicable

    def max_theoretical_raw(self) -> float:
        by_family: dict[str, float] = {}
        for edge in self._edges:
            by_family[edge.family] = max(by_family.get(edge.family, 0.0), edge.weight)
        return sum(by_family.values()) or 1.0

    def score_signals(self, signals: pd.DataFrame) -> pd.DataFrame:
        max_raw = self._config.max_theoretical_score or self.max_theoretical_raw()
        scores: list[float] = []
        raw_scores: list[float] = []
        vote_counts: list[int] = []
        family_counts: list[int] = []
        matching_rules: list[str] = []

        for idx in signals.index:
            row_frame = signals.loc[[idx]]
            raw, families, matches = self._score_row(row_frame)
            consensus = 0.0 if max_raw <= 0 else min(100.0, (raw / max_raw) * 100.0)
            scores.append(round(consensus, 2))
            raw_scores.append(round(raw, 4))
            vote_counts.append(len(matches))
            family_counts.append(len(families))
            matching_rules.append(";".join(matches[:8]))

        out = signals.copy()
        out["Raw_Vote_Score"] = raw_scores
        out["Edge_Consensus_Score"] = scores
        out["Matching_Edge_Count"] = vote_counts
        out["Matching_Family_Count"] = family_counts
        out["Matching_Rules_Sample"] = matching_rules
        return out

    def _score_row(self, row_frame: pd.DataFrame) -> tuple[float, set[str], list[str]]:
        family_weights: dict[str, list[float]] = {}
        family_rules: dict[str, list[str]] = {}
        for edge in self._edges:
            if not self._rule_matches(edge, row_frame):
                continue
            family_weights.setdefault(edge.family, []).append(edge.weight)
            family_rules.setdefault(edge.family, []).append(edge.rule_id)

        raw = 0.0
        matches: list[str] = []
        dup_penalty = self._config.family_duplicate_weight
        for family, weights in family_weights.items():
            ordered = sorted(weights, reverse=True)
            contribution = ordered[0]
            for extra in ordered[1:]:
                contribution += extra * dup_penalty
            raw += contribution
            matches.extend(family_rules.get(family, [])[:3])

        return raw, set(family_weights.keys()), matches

    def _rule_matches(self, edge: SurvivorEdge, row_frame: pd.DataFrame) -> bool:
        for col in edge.bin_columns:
            if col not in row_frame.columns:
                return False
            value = row_frame[col].iloc[0]
            if pd.isna(value):
                return False
            if not bool(value):
                return False
        return True


class BucketAnalyzer:
    """Bucket stats, monotonicity, and correlation."""

    def __init__(self, baseline: dict[str, Any]) -> None:
        self._baseline = baseline

    def assign_bucket(self, score: float) -> str:
        for label, low, high in BUCKETS:
            if low <= score < high:
                return label
        return BUCKETS[-1][0]

    def bucket_stats(self, scored: pd.DataFrame) -> pd.DataFrame:
        scored = scored.copy()
        scored["Consensus_Bucket"] = scored["Edge_Consensus_Score"].apply(self.assign_bucket)
        rows: list[dict[str, Any]] = []
        for label, low, high in BUCKETS:
            sub = scored[
                (scored["Edge_Consensus_Score"] >= low)
                & (scored["Edge_Consensus_Score"] < high)
            ]
            rets = sub[RETURN_COL].astype(float).values
            metrics = compute_metrics(rets, self._baseline)
            metrics.update(
                {
                    "Bucket": label,
                    "Bucket_Low": low,
                    "Bucket_High": high if high < 100 else 100,
                    "MAE_Median": round(float(sub["MAE"].median()), 4) if len(sub) else None,
                    "MFE_Median": round(float(sub["MFE"].median()), 4) if len(sub) else None,
                }
            )
            rows.append(metrics)
        return pd.DataFrame(rows)

    def correlation(self, scored: pd.DataFrame) -> float:
        valid = scored[[ "Edge_Consensus_Score", RETURN_COL]].dropna()
        if len(valid) < 2:
            return 0.0
        return float(valid["Edge_Consensus_Score"].corr(valid[RETURN_COL]))

    def monotonicity_check(self, bucket_df: pd.DataFrame) -> tuple[bool, int, list[float]]:
        avgs = []
        for label in [b[0] for b in BUCKETS]:
            row = bucket_df[bucket_df["Bucket"] == label]
            if row.empty or row.iloc[0]["Trades"] == 0:
                avgs.append(np.nan)
            else:
                avgs.append(float(row.iloc[0]["Avg_Return"]))
        increases = 0
        pairs = 0
        for i in range(len(avgs) - 1):
            if np.isnan(avgs[i]) or np.isnan(avgs[i + 1]):
                continue
            pairs += 1
            if avgs[i + 1] > avgs[i]:
                increases += 1
        mostly_positive = pairs > 0 and increases >= max(2, pairs - 1)
        return mostly_positive, increases, avgs


class VerdictEngine:
    """Final ensemble research verdict."""

    def decide(
        self,
        baseline: dict[str, Any],
        bucket_df: pd.DataFrame,
        correlation: float,
        monotonic: bool,
    ) -> tuple[str, str]:
        ranked = bucket_df[bucket_df["Trades"] > 0].sort_values("Avg_Return", ascending=False)
        if ranked.empty:
            return "ENSEMBLE_NO_CLEAR_EDGE", "No bucket with trades."

        top = ranked.iloc[0]
        top_bucket = str(top["Bucket"])
        confirmed = (
            int(top["Trades"]) >= 100
            and float(top["Avg_Return"]) > float(baseline["Avg_Return"]) + 3.0
            and float(top["Win_Rate"]) > float(baseline["Win_Rate"]) + 5.0
            and float(top["Profit_Factor"]) > float(baseline["Profit_Factor"])
            and monotonic
        )
        partial = (
            int(top["Trades"]) >= 50
            and float(top["Avg_Return"]) > float(baseline["Avg_Return"])
            and correlation > 0.05
        )

        detail = (
            f"Top bucket={top_bucket} trades={int(top['Trades'])} "
            f"avg={top['Avg_Return']}% win={top['Win_Rate']}% "
            f"corr={round(correlation, 4)} monotonic={monotonic}"
        )
        if confirmed:
            return "ENSEMBLE_EDGE_CONFIRMED", detail
        if partial:
            return "ENSEMBLE_PARTIAL_EDGE", detail
        return "ENSEMBLE_NO_CLEAR_EDGE", detail


class EnsembleReporter:
    """Write CSV outputs and summary text."""

    def __init__(self, config: EnsembleConfig) -> None:
        self._config = config

    def write(
        self,
        scored: pd.DataFrame,
        bucket_df: pd.DataFrame,
        baseline: dict[str, Any],
        edges: list[SurvivorEdge],
        families: dict[str, int],
        correlation: float,
        monotonic: bool,
        monotonic_increases: int,
        avg_by_bucket: list[float],
        verdict: str,
        verdict_detail: str,
    ) -> str:
        out_dir = self._config.output_dir
        scores_path = out_dir / SIGNAL_SCORES_CSV
        bucket_path = out_dir / BUCKET_STATS_CSV
        summary_path = out_dir / SUMMARY_TXT

        score_cols = [
            c for c in scored.columns
            if not c.startswith("BIN_")
        ]
        scored[score_cols].to_csv(scores_path, index=False)
        bucket_df.to_csv(bucket_path, index=False)

        top_bucket_row = bucket_df.sort_values("Avg_Return", ascending=False).iloc[0]
        lines = [
            "===== EDGE ENSEMBLE ENGINE V3.1 =====",
            "",
            RESEARCH_SAFETY_BANNER,
            "Research only — no broker, no execution, no production promotion.",
            "",
            f"Survivor edges loaded: {len(edges)}",
            f"Edge families represented: {len(families)}",
            "",
            "--- Family distribution ---",
        ]
        for family, count in sorted(families.items(), key=lambda x: -x[1]):
            lines.append(f"  {family}: {count}")
        lines.extend(
            [
                "",
                "--- Baseline (all momentum signals) ---",
                f"  Trades: {baseline['Trades']}",
                f"  Win_Rate: {baseline['Win_Rate']}%",
                f"  Avg_Return: {baseline['Avg_Return']}%",
                f"  Median_Return: {baseline.get('Median_Return')}",
                f"  Profit_Factor: {baseline['Profit_Factor']}",
                f"  Worst_Trade: {baseline.get('Worst_Trade')}",
                "",
                "--- Bucket statistics ---",
            ]
        )
        for _, row in bucket_df.iterrows():
            lines.append(
                f"  {row['Bucket']}: trades={int(row['Trades'])} "
                f"win={row['Win_Rate']}% avg={row['Avg_Return']}% "
                f"pf={row['Profit_Factor']}"
            )
        lines.extend(
            [
                "",
                f"Top consensus bucket (by Avg_Return): {top_bucket_row['Bucket']}",
                f"  Trades: {int(top_bucket_row['Trades'])}",
                f"  Avg_Return: {top_bucket_row['Avg_Return']}%",
                f"  Win_Rate: {top_bucket_row['Win_Rate']}%",
                f"  Profit_Factor: {top_bucket_row['Profit_Factor']}",
                "",
                "--- Score vs return relationship ---",
                f"Correlation (Edge_Consensus_Score vs {RETURN_COL}): {round(correlation, 4)}",
                f"Monotonicity mostly positive: {monotonic}",
                f"Monotonic increases across buckets: {monotonic_increases}",
                f"Avg_Return by bucket (low→high): {avg_by_bucket}",
                "",
                f"FINAL VERDICT: {verdict}",
                verdict_detail,
                "",
                f"Saved: {scores_path}",
                f"Saved: {bucket_path}",
                f"Saved: {summary_path}",
                "",
            ]
        )
        summary = "\n".join(lines)
        summary_path.write_text(summary, encoding="utf-8")
        print(summary)
        return summary


class EnsembleEngine:
    """Orchestrates V3.1 edge ensemble research run."""

    def __init__(self, config: EnsembleConfig | None = None) -> None:
        self.config = config or EnsembleConfig()

    def run(self) -> dict[str, Any]:
        print("===== EDGE ENSEMBLE ENGINE V3.1 =====")
        print(RESEARCH_SAFETY_BANNER)
        print()

        loader = SurvivorLoader(self.config)
        edges = loader.load()
        print(f"Loaded {len(edges)} survivor edges.")

        required_bins = {col for edge in edges for col in edge.bin_columns}
        signal_loader = SignalFrameLoader(self.config)
        signals = signal_loader.load(required_bins)
        print(f"Loaded {len(signals)} signals for scoring.")

        baseline_rets = signals[RETURN_COL].astype(float).values
        baseline = compute_metrics(baseline_rets, {"Avg_Return": 0, "Win_Rate": 0})
        print(
            f"Baseline: trades={baseline['Trades']} win={baseline['Win_Rate']}% "
            f"avg={baseline['Avg_Return']}% pf={baseline['Profit_Factor']}"
        )

        scorer = ConsensusScorer(self.config, edges)
        scored = scorer.score_signals(signals)

        families: dict[str, int] = {}
        for edge in edges:
            families[edge.family] = families.get(edge.family, 0) + 1

        analyzer = BucketAnalyzer(baseline)
        bucket_df = analyzer.bucket_stats(scored)
        correlation = analyzer.correlation(scored)
        monotonic, mono_increases, avg_by_bucket = analyzer.monotonicity_check(bucket_df)

        verdict, verdict_detail = VerdictEngine().decide(
            baseline, bucket_df, correlation, monotonic
        )

        reporter = EnsembleReporter(self.config)
        reporter.write(
            scored=scored,
            bucket_df=bucket_df,
            baseline=baseline,
            edges=edges,
            families=families,
            correlation=correlation,
            monotonic=monotonic,
            monotonic_increases=mono_increases,
            avg_by_bucket=avg_by_bucket,
            verdict=verdict,
            verdict_detail=verdict_detail,
        )

        return {
            "status": "ok",
            "survivors": len(edges),
            "signals": len(scored),
            "verdict": verdict,
            "correlation": correlation,
        }


def main() -> None:
    EnsembleEngine().run()


if __name__ == "__main__":
    main()
