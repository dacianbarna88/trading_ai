"""
Momentum research organism — ensemble / V1.8 momentum features on the TAE bus.

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | ANALYSIS_ONLY

Uses evidence_engine_v40 momentum evaluation plus volume impulse from research CSVs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from evidence_engine_v40 import MomentumEvidenceEvaluator, VolumeEvidenceEvaluator
from research_core.ecosystem.evidence_packet import EvidencePacket
from research_core.ecosystem.organism import Organism
from research_core.ecosystem.organisms.research_signal_loader import (
    DEFAULT_ENSEMBLE_SCORES,
    DEFAULT_V18_FEATURES,
    format_signal_date,
    load_research_csv,
    pick_signal_row,
    safe_float,
)

ORGANISM_NAME = "momentum_research_organism"


class MomentumOrganism(Organism):
    """Evaluates momentum impulse from ensemble scores or V1.8 feature fallback."""

    def __init__(
        self,
        ensemble_path: Path | None = None,
        fallback_features_path: Path | None = None,
    ) -> None:
        self._ensemble_path = ensemble_path or DEFAULT_ENSEMBLE_SCORES
        self._fallback_path = fallback_features_path or DEFAULT_V18_FEATURES
        self._trust: float = 64.0
        self._cycles: int = 0
        self._last_learning: str = ""
        self._load_error: str | None = None
        self._signals: pd.DataFrame | None = None
        self._current_row: pd.Series | None = None
        self._last_analysis: dict[str, Any] | None = None
        self._signal_count: int = 0
        self._momentum_eval = MomentumEvidenceEvaluator()
        self._volume_eval = VolumeEvidenceEvaluator()

    @property
    def name(self) -> str:
        return ORGANISM_NAME

    def _ensure_loaded(self) -> None:
        if self._signals is not None or self._load_error is not None:
            return
        signals, error = load_research_csv(self._ensemble_path)
        if signals is None:
            signals, fallback_error = load_research_csv(self._fallback_path)
            if signals is None:
                self._load_error = error or fallback_error or "No momentum data available."
                return
        self._signals = signals
        self._signal_count = len(signals)

    def observe(self) -> dict[str, Any]:
        self._cycles += 1
        self._ensure_loaded()

        if self._signals is None or self._signals.empty:
            return {
                "cycle": self._cycles,
                "error": self._load_error or "No momentum signals available.",
                "source": "momentum_research",
            }

        sort_col = "Edge_Consensus_Score" if "Edge_Consensus_Score" in self._signals.columns else "Daily_Gain_Pct"
        row = pick_signal_row(self._signals, self._cycles, sort_col, ascending=False)
        self._current_row = row

        daily_gain = safe_float(row.get("Daily_Gain_Pct"), 0.0) or 0.0
        volume_ratio = safe_float(row.get("Volume_Ratio"), 0.0) or 0.0

        return {
            "cycle": self._cycles,
            "source": "momentum_research",
            "ticker": str(row.get("Ticker", "")),
            "signal_date": format_signal_date(row.get("Signal_Date")),
            "daily_gain_pct": daily_gain,
            "volume_ratio": volume_ratio,
            "edge_consensus": safe_float(row.get("Edge_Consensus_Score")),
            "matching_edges": int(row.get("Matching_Edge_Count", 0) or 0),
            "market_regime": str(row.get("Market_Regime", "NEUTRAL")),
            "impulse_strength": self._impulse_label(daily_gain, volume_ratio),
            "signals_available": self._signal_count,
        }

    def _impulse_label(self, daily_gain: float, volume_ratio: float) -> str:
        if daily_gain >= 10 and volume_ratio >= 2.0:
            return "strong_burst"
        if daily_gain >= 7:
            return "elevated"
        if daily_gain >= 5:
            return "minimum_filter"
        return "weak"

    def analyze(self, observations: dict[str, Any]) -> dict[str, Any]:
        if observations.get("error"):
            return {
                "error": observations["error"],
                "momentum_score": 25.0,
                "ticker": "",
                "signal_date": "",
                "market_regime": "NEUTRAL",
                "recommended_action": "CONTINUE_OBSERVATION",
            }

        if self._current_row is None:
            return {
                "error": "Momentum row not selected.",
                "momentum_score": 25.0,
                "ticker": observations.get("ticker", ""),
                "signal_date": observations.get("signal_date", ""),
                "market_regime": observations.get("market_regime", "NEUTRAL"),
                "recommended_action": "CONTINUE_OBSERVATION",
            }

        momentum_ev = self._momentum_eval.evaluate(self._current_row)
        volume_ev = self._volume_eval.evaluate(self._current_row)
        combined = round((momentum_ev.score * 0.7 + volume_ev.score * 0.3), 2)

        edge_consensus = observations.get("edge_consensus")
        if edge_consensus is not None and edge_consensus >= 80:
            combined = min(100.0, combined + 5.0)

        impulse = observations.get("impulse_strength", "weak")
        if impulse == "strong_burst":
            action = "MOMENTUM_CONTINUATION_WATCH"
        elif impulse == "elevated":
            action = "MOMENTUM_RESEARCH_CANDIDATE"
        elif impulse == "minimum_filter":
            action = "CONTINUE_OBSERVATION"
        else:
            action = "REDUCE_MOMENTUM_WEIGHT"

        analysis = {
            "ticker": observations.get("ticker", ""),
            "signal_date": observations.get("signal_date", ""),
            "market_regime": observations.get("market_regime", "NEUTRAL"),
            "momentum_score": combined,
            "momentum_component": momentum_ev.score,
            "volume_component": volume_ev.score,
            "momentum_explanation": momentum_ev.explanation,
            "volume_explanation": volume_ev.explanation,
            "daily_gain_pct": observations.get("daily_gain_pct", 0),
            "volume_ratio": observations.get("volume_ratio", 0),
            "edge_consensus": edge_consensus,
            "matching_edges": observations.get("matching_edges", 0),
            "impulse_strength": impulse,
            "recommended_action": action,
            "signals_available": observations.get("signals_available", self._signal_count),
        }
        self._last_analysis = analysis
        return analysis

    def produce_evidence(self, analysis: dict[str, Any]) -> EvidencePacket:
        if analysis.get("error"):
            return EvidencePacket.create(
                organism_name=self.name,
                observation_summary=f"Momentum research unavailable: {analysis['error'][:120]}",
                confidence=20.0,
                trust=self._trust,
                explanation=self.explain(analysis),
                supporting_features={
                    "source": "momentum_research",
                    "error": True,
                    "market_regime": "NEUTRAL",
                },
                recommended_action="CONTINUE_OBSERVATION",
            )

        ticker = analysis.get("ticker", "UNKNOWN")
        signal_date = analysis.get("signal_date", "")
        score = float(analysis.get("momentum_score", 25.0))
        regime = analysis.get("market_regime", "NEUTRAL")
        impulse = analysis.get("impulse_strength", "weak")

        return EvidencePacket.create(
            organism_name=self.name,
            observation_summary=(
                f"{ticker} {signal_date}: momentum {score:.1f} "
                f"gain={analysis.get('daily_gain_pct', 0):.1f}% impulse={impulse}"
            ),
            confidence=score,
            trust=self._trust,
            explanation=self.explain(analysis),
            supporting_features={
                "source": "momentum_research",
                "ticker": ticker,
                "signal_date": signal_date,
                "regime": regime,
                "market_regime": regime,
                "daily_gain_pct": analysis.get("daily_gain_pct"),
                "volume_ratio": analysis.get("volume_ratio"),
                "impulse_strength": impulse,
                "edge_consensus": analysis.get("edge_consensus"),
                "matching_edges": analysis.get("matching_edges"),
                "high_volatility": float(analysis.get("daily_gain_pct", 0) or 0) > 8.0,
                "volatility_regime": "HIGH" if float(analysis.get("daily_gain_pct", 0) or 0) > 8.0 else "NORMAL",
            },
            recommended_action=str(analysis.get("recommended_action", "CONTINUE_OBSERVATION")),
            knowledge_reference=f"momentum_research_{ticker}_{signal_date}_{impulse}".replace(" ", "_"),
        )

    def explain(self, analysis: dict[str, Any]) -> str:
        if analysis.get("error"):
            return f"Momentum research unavailable: {analysis['error']}"
        parts = [
            f"Momentum research for {analysis.get('ticker')} on {analysis.get('signal_date')}: "
            f"combined score {analysis.get('momentum_score', 0):.1f}.",
            str(analysis.get("momentum_explanation", "")),
            str(analysis.get("volume_explanation", "")),
        ]
        if analysis.get("edge_consensus") is not None:
            parts.append(f"Edge consensus {analysis.get('edge_consensus'):.1f}.")
        return " ".join(parts)

    def learn(self, feedback: dict[str, Any]) -> dict[str, Any]:
        self._last_learning = feedback.get("lesson", feedback.get("summary", "Momentum organism learned."))
        return {"organism": self.name, "learning": self._last_learning}

    def receive_feedback(self, feedback: dict[str, Any]) -> None:
        if "trust_delta" in feedback:
            self.update_trust(float(feedback["trust_delta"]), feedback.get("reason", "feedback"))

    def update_trust(self, delta: float, reason: str) -> float:
        self._trust = max(0.0, min(100.0, self._trust + delta))
        return self._trust

    def health_status(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._load_error is None else "degraded",
            "cycles_completed": self._cycles,
            "trust": self._trust,
            "signals_available": self._signal_count,
            "load_error": self._load_error,
            "last_learning": self._last_learning,
            "last_momentum_score": (
                self._last_analysis.get("momentum_score") if self._last_analysis else None
            ),
        }

    def last_analysis(self) -> dict[str, Any] | None:
        return dict(self._last_analysis) if self._last_analysis else None
