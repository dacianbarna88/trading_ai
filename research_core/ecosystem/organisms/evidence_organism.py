"""
Evidence Engine V4.0 organism — first real research module on the TAE bus.

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | ANALYSIS_ONLY

Wraps evidence_engine_v40 dossier logic. Reads ensemble research outputs only —
no broker, no order execution, no live bot integration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from evidence_engine_v40 import (
    EvidenceConfig,
    EvidenceDataLoader,
    DossierBuilder,
)
from research_core.ecosystem.evidence_packet import EvidencePacket
from research_core.ecosystem.organism import Organism

ORGANISM_NAME = "evidence_engine_v40_organism"

DECISION_ACTIONS: dict[str, str] = {
    "HIGH_CONVICTION_PAPER_CANDIDATE": "PAPER_RESEARCH_HIGH_CONVICTION",
    "PAPER_CANDIDATE": "PAPER_RESEARCH_CANDIDATE",
    "WATCH": "CONTINUE_OBSERVATION",
    "IGNORE": "REDUCE_ATTENTION",
}


class EvidenceOrganism(Organism):
    """
    Live organism that evaluates real ensemble signals through Evidence Engine V4.0.
    """

    def __init__(self, config: EvidenceConfig | None = None) -> None:
        self._config = config or EvidenceConfig()
        self._trust: float = 72.0
        self._cycles: int = 0
        self._last_learning: str = ""
        self._load_error: str | None = None
        self._signals: pd.DataFrame | None = None
        self._builder: DossierBuilder | None = None
        self._current_row: pd.Series | None = None
        self._last_dossier: dict[str, Any] | None = None
        self._signal_count: int = 0
        self._favored_regime: str = "BEAR"

    @property
    def name(self) -> str:
        return ORGANISM_NAME

    def _ensure_loaded(self) -> None:
        if self._signals is not None or self._load_error is not None:
            return
        try:
            loader = EvidenceDataLoader(self._config)
            self._signals = loader.load_signals()
            bucket_lookup = loader.load_bucket_lookup()
            self._favored_regime = loader.load_survivor_regime_bias()
            self._builder = DossierBuilder(self._config, bucket_lookup, self._favored_regime)
            self._signal_count = len(self._signals)
        except (FileNotFoundError, ValueError, OSError) as exc:
            self._load_error = str(exc)
            self._signals = None
            self._builder = None

    def observe(self) -> dict[str, Any]:
        self._cycles += 1
        self._ensure_loaded()

        if self._signals is None or self._signals.empty:
            return {
                "cycle": self._cycles,
                "error": self._load_error or "No ensemble signals available.",
                "source": "evidence_engine_v40",
            }

        ranked = self._signals.sort_values("Edge_Consensus_Score", ascending=False)
        pick_index = min(self._cycles - 1, len(ranked) - 1)
        row = ranked.iloc[pick_index]
        self._current_row = row

        signal_date = row.get("Signal_Date")
        if isinstance(signal_date, datetime):
            signal_date_str = signal_date.strftime("%Y-%m-%d")
        else:
            signal_date_str = str(signal_date)

        return {
            "cycle": self._cycles,
            "source": "evidence_engine_v40",
            "ticker": str(row.get("Ticker", "")),
            "signal_date": signal_date_str,
            "edge_consensus": float(row.get("Edge_Consensus_Score", 0) or 0),
            "market_regime": str(row.get("Market_Regime", "NEUTRAL")),
            "matching_edges": int(row.get("Matching_Edge_Count", 0) or 0),
            "signals_available": self._signal_count,
            "favored_regime": self._favored_regime,
        }

    def analyze(self, observations: dict[str, Any]) -> dict[str, Any]:
        if observations.get("error"):
            return {
                "error": observations["error"],
                "overall_score": 25.0,
                "decision_label": "IGNORE",
                "risk_level": "HIGH",
                "ticker": "",
                "signal_date": "",
                "market_regime": "NEUTRAL",
            }

        if self._current_row is None or self._builder is None:
            return {
                "error": "Evidence engine not initialized.",
                "overall_score": 25.0,
                "decision_label": "IGNORE",
                "risk_level": "HIGH",
                "ticker": observations.get("ticker", ""),
                "signal_date": observations.get("signal_date", ""),
                "market_regime": observations.get("market_regime", "NEUTRAL"),
            }

        dossier_df = self._builder.build(pd.DataFrame([self._current_row]))
        dossier = dossier_df.iloc[0].to_dict()
        self._last_dossier = dossier

        return {
            "ticker": str(dossier.get("Ticker", observations.get("ticker", ""))),
            "signal_date": str(dossier.get("Signal_Date", observations.get("signal_date", ""))),
            "overall_score": float(dossier.get("Overall_Evidence_Score", 0) or 0),
            "decision_label": str(dossier.get("Decision_Label", "IGNORE")),
            "risk_level": str(dossier.get("Risk_Level", "MEDIUM")),
            "edge_consensus": float(dossier.get("Edge_Consensus_Score", 0) or 0),
            "matching_edges": int(dossier.get("Matching_Edge_Count", 0) or 0),
            "market_regime": str(
                self._current_row.get("Market_Regime", observations.get("market_regime", "NEUTRAL"))
            ),
            "momentum_score": float(dossier.get("Momentum_Evidence_Score", 0) or 0),
            "market_context_score": float(dossier.get("Market_Context_Evidence_Score", 0) or 0),
            "conflict_score": float(dossier.get("Conflict_Evidence_Score", 0) or 0),
            "conflict_penalty": float(dossier.get("Conflict_Penalty_Applied", 0) or 0),
            "estimated_probability": dossier.get("Estimated_Probability_Positive"),
            "expected_return_bucket": dossier.get("Expected_Return_Bucket"),
            "momentum_explanation": str(dossier.get("Momentum_Explanation", "")),
            "market_context_explanation": str(dossier.get("Market_Context_Explanation", "")),
            "conflict_explanation": str(dossier.get("Conflict_Explanation", "")),
            "favored_regime": observations.get("favored_regime", self._favored_regime),
            "signals_available": observations.get("signals_available", self._signal_count),
        }

    def produce_evidence(self, analysis: dict[str, Any]) -> EvidencePacket:
        ticker = analysis.get("ticker", "UNKNOWN")
        signal_date = analysis.get("signal_date", "")
        decision = analysis.get("decision_label", "IGNORE")
        overall = float(analysis.get("overall_score", 25.0))

        if analysis.get("error"):
            return EvidencePacket.create(
                organism_name=self.name,
                observation_summary=f"Evidence Engine unavailable: {analysis['error'][:120]}",
                confidence=20.0,
                trust=self._trust,
                explanation=self.explain(analysis),
                supporting_features={
                    "source": "evidence_engine_v40",
                    "error": True,
                    "market_regime": "NEUTRAL",
                },
                recommended_action="CONTINUE_OBSERVATION",
                knowledge_reference=None,
            )

        knowledge_ref = f"evidence_v40_{ticker}_{signal_date}".replace(" ", "_")
        regime = str(analysis.get("market_regime", "NEUTRAL"))
        atr_pct = None
        if self._current_row is not None:
            atr_pct = self._current_row.get("ATR_Pct") or self._current_row.get("ATR_14_Pct")

        return EvidencePacket.create(
            organism_name=self.name,
            observation_summary=(
                f"{ticker} {signal_date}: Evidence V4.0 {decision} "
                f"(score={overall:.1f}, consensus={analysis.get('edge_consensus', 0):.1f})"
            ),
            confidence=overall,
            trust=self._trust,
            explanation=self.explain(analysis),
            supporting_features={
                "source": "evidence_engine_v40",
                "ticker": ticker,
                "signal_date": signal_date,
                "decision_label": decision,
                "risk_level": analysis.get("risk_level", "MEDIUM"),
                "edge_consensus": analysis.get("edge_consensus", 0),
                "matching_edges": analysis.get("matching_edges", 0),
                "regime": regime,
                "market_regime": regime,
                "favored_regime": analysis.get("favored_regime", self._favored_regime),
                "momentum_score": analysis.get("momentum_score", 0),
                "market_context_score": analysis.get("market_context_score", 0),
                "conflict_score": analysis.get("conflict_score", 0),
                "conflict_penalty": analysis.get("conflict_penalty", 0),
                "signals_evaluated": analysis.get("signals_available", self._signal_count),
                "high_volatility": float(atr_pct or 0) > 3.0,
                "volatility_regime": "HIGH" if float(atr_pct or 0) > 3.0 else "NORMAL",
            },
            recommended_action=DECISION_ACTIONS.get(decision, "CONTINUE_OBSERVATION"),
            knowledge_reference=knowledge_ref,
        )

    def explain(self, analysis: dict[str, Any]) -> str:
        if analysis.get("error"):
            return f"Evidence Engine V4.0 could not evaluate signals: {analysis['error']}"

        parts = [
            f"Evidence Engine V4.0 dossier for {analysis.get('ticker')} on {analysis.get('signal_date')}.",
            f"Decision: {analysis.get('decision_label')} (overall {analysis.get('overall_score', 0):.1f}).",
            f"Edge consensus {analysis.get('edge_consensus', 0):.1f} with "
            f"{analysis.get('matching_edges', 0)} matching survivor rules.",
            f"Regime {analysis.get('market_regime')} vs favored {analysis.get('favored_regime')}.",
        ]
        if analysis.get("momentum_explanation"):
            parts.append(str(analysis["momentum_explanation"]))
        if analysis.get("conflict_explanation"):
            parts.append(str(analysis["conflict_explanation"]))
        return " ".join(parts)

    def learn(self, feedback: dict[str, Any]) -> dict[str, Any]:
        self._last_learning = feedback.get("lesson", feedback.get("summary", "Evidence organism learned."))
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
            "last_decision": (
                self._last_dossier.get("Decision_Label") if self._last_dossier else None
            ),
        }

    def last_dossier(self) -> dict[str, Any] | None:
        return dict(self._last_dossier) if self._last_dossier else None
