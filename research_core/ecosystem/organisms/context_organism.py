"""
Context research organism — V1.8 context features on the TAE bus.

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | ANALYSIS_ONLY

Lightweight wrapper over context_v18_signal_features.csv and pattern rankings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from research_core.ecosystem.evidence_packet import EvidencePacket
from research_core.ecosystem.organism import Organism
from research_core.ecosystem.organisms.research_signal_loader import (
    DEFAULT_V18_FEATURES,
    DEFAULT_V18_PATTERNS,
    format_signal_date,
    load_research_csv,
    pick_signal_row,
    safe_float,
)

ORGANISM_NAME = "context_research_organism"


class ContextOrganism(Organism):
    """Evaluates market regime and SPY context from V1.8 research features."""

    def __init__(
        self,
        features_path: Path | None = None,
        patterns_path: Path | None = None,
    ) -> None:
        self._features_path = features_path or DEFAULT_V18_FEATURES
        self._patterns_path = patterns_path or DEFAULT_V18_PATTERNS
        self._trust: float = 58.0
        self._cycles: int = 0
        self._last_learning: str = ""
        self._load_error: str | None = None
        self._features: pd.DataFrame | None = None
        self._patterns: pd.DataFrame | None = None
        self._current_row: pd.Series | None = None
        self._last_analysis: dict[str, Any] | None = None
        self._signal_count: int = 0

    @property
    def name(self) -> str:
        return ORGANISM_NAME

    def _ensure_loaded(self) -> None:
        if self._features is not None or self._load_error is not None:
            return
        features, error = load_research_csv(self._features_path)
        if features is None:
            self._load_error = error
            return
        self._features = features
        self._signal_count = len(features)
        patterns, _ = load_research_csv(self._patterns_path)
        self._patterns = patterns

    def observe(self) -> dict[str, Any]:
        self._cycles += 1
        self._ensure_loaded()

        if self._features is None or self._features.empty:
            return {
                "cycle": self._cycles,
                "error": self._load_error or "No context features available.",
                "source": "context_v18",
            }

        row = pick_signal_row(self._features, self._cycles, "Daily_Gain_Pct", ascending=False)
        self._current_row = row

        return {
            "cycle": self._cycles,
            "source": "context_v18",
            "ticker": str(row.get("Ticker", "")),
            "signal_date": format_signal_date(row.get("Signal_Date")),
            "market_regime": str(row.get("Market_Regime", "NEUTRAL")),
            "rsi_14": safe_float(row.get("RSI_14")),
            "spy_vs_sma200": safe_float(row.get("SPY_Close_vs_SMA200_Pct")),
            "spy_60d_return": safe_float(row.get("SPY_60d_Return_Pct")),
            "spy_atr_pct": safe_float(row.get("SPY_ATR_14_Pct")),
            "signals_available": self._signal_count,
        }

    def analyze(self, observations: dict[str, Any]) -> dict[str, Any]:
        if observations.get("error"):
            return {
                "error": observations["error"],
                "context_score": 25.0,
                "ticker": "",
                "signal_date": "",
                "market_regime": "NEUTRAL",
                "recommended_action": "CONTINUE_OBSERVATION",
            }

        regime = str(observations.get("market_regime", "NEUTRAL"))
        rsi = observations.get("rsi_14")
        spy_vs = observations.get("spy_vs_sma200")
        spy_60 = observations.get("spy_60d_return")
        spy_atr = observations.get("spy_atr_pct") or 0.0

        score = 55.0
        reasons: list[str] = []

        if regime == "BEAR":
            score += 18.0
            reasons.append("BEAR regime aligns with validated context-edge research bias.")
        elif regime == "BULL":
            score -= 12.0
            reasons.append("BULL regime — survivor context edges historically favor BEAR.")
        else:
            reasons.append("NEUTRAL regime — mixed historical edge performance.")

        if rsi is not None and rsi < 40:
            score += 15.0
            reasons.append(f"RSI {rsi:.1f} < 40 matches V1.8 oversold context candidate.")
        elif rsi is not None and rsi > 70:
            score -= 10.0
            reasons.append(f"RSI {rsi:.1f} overbought — caution for oversold-edge rules.")

        if spy_vs is not None and spy_vs < 0:
            score += 8.0
            reasons.append(f"SPY {spy_vs:.1f}% below SMA200 — defensive macro backdrop.")
        if spy_60 is not None and spy_60 < 0:
            score += 5.0
            reasons.append(f"SPY 60d return {spy_60:.1f}% negative.")

        pattern_match = self._match_pattern(regime, rsi)
        if pattern_match:
            score += 6.0
            reasons.append(f"Pattern hint: {pattern_match}")

        score = max(0.0, min(100.0, round(score, 2)))
        volatility_regime = "HIGH" if spy_atr > 1.5 else "NORMAL"

        if score >= 75:
            action = "ELEVATE_CONTEXT_ATTENTION"
        elif score >= 55:
            action = "CONTINUE_OBSERVATION"
        else:
            action = "REDUCE_CONTEXT_WEIGHT"

        analysis = {
            "ticker": observations.get("ticker", ""),
            "signal_date": observations.get("signal_date", ""),
            "market_regime": regime,
            "context_score": score,
            "rsi_14": rsi,
            "spy_vs_sma200": spy_vs,
            "spy_60d_return": spy_60,
            "spy_atr_pct": spy_atr,
            "volatility_regime": volatility_regime,
            "pattern_match": pattern_match,
            "reasons": reasons,
            "recommended_action": action,
            "signals_available": observations.get("signals_available", self._signal_count),
        }
        self._last_analysis = analysis
        return analysis

    def _match_pattern(self, regime: str, rsi: float | None) -> str | None:
        if regime == "BEAR" and rsi is not None and rsi < 40:
            return "RSI_14 < 40 + Market_Regime = BEAR (V1.8 candidate)"
        if self._patterns is None or self._patterns.empty:
            return None
        bear_rows = self._patterns[
            self._patterns["Condition"].astype(str).str.contains("BEAR", case=False, na=False)
        ]
        if not bear_rows.empty:
            top = bear_rows.sort_values("Avg_Return", ascending=False).iloc[0]
            return str(top.get("Condition", ""))[:80]
        return None

    def produce_evidence(self, analysis: dict[str, Any]) -> EvidencePacket:
        if analysis.get("error"):
            return EvidencePacket.create(
                organism_name=self.name,
                observation_summary=f"Context research unavailable: {analysis['error'][:120]}",
                confidence=20.0,
                trust=self._trust,
                explanation=self.explain(analysis),
                supporting_features={
                    "source": "context_v18",
                    "error": True,
                    "market_regime": "NEUTRAL",
                },
                recommended_action="CONTINUE_OBSERVATION",
            )

        regime = analysis.get("market_regime", "NEUTRAL")
        ticker = analysis.get("ticker", "UNKNOWN")
        signal_date = analysis.get("signal_date", "")
        score = float(analysis.get("context_score", 25.0))

        return EvidencePacket.create(
            organism_name=self.name,
            observation_summary=(
                f"{ticker} {signal_date}: {regime} context score {score:.1f} "
                f"(RSI={analysis.get('rsi_14', 'n/a')})"
            ),
            confidence=score,
            trust=self._trust,
            explanation=self.explain(analysis),
            supporting_features={
                "source": "context_v18",
                "ticker": ticker,
                "signal_date": signal_date,
                "regime": regime,
                "market_regime": regime,
                "rsi_14": analysis.get("rsi_14"),
                "spy_vs_sma200": analysis.get("spy_vs_sma200"),
                "volatility_regime": analysis.get("volatility_regime", "NORMAL"),
                "high_volatility": analysis.get("volatility_regime") == "HIGH",
                "pattern_match": analysis.get("pattern_match"),
            },
            recommended_action=str(analysis.get("recommended_action", "CONTINUE_OBSERVATION")),
            knowledge_reference=f"context_v18_{regime}_{ticker}_{signal_date}".replace(" ", "_"),
        )

    def explain(self, analysis: dict[str, Any]) -> str:
        if analysis.get("error"):
            return f"Context V1.8 research unavailable: {analysis['error']}"
        reasons = analysis.get("reasons", [])
        base = (
            f"Context research for {analysis.get('ticker')} on {analysis.get('signal_date')}: "
            f"regime {analysis.get('market_regime')} score {analysis.get('context_score', 0):.1f}."
        )
        if reasons:
            return base + " " + " ".join(reasons)
        return base

    def learn(self, feedback: dict[str, Any]) -> dict[str, Any]:
        self._last_learning = feedback.get("lesson", feedback.get("summary", "Context organism learned."))
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
            "last_context_score": (
                self._last_analysis.get("context_score") if self._last_analysis else None
            ),
        }

    def last_analysis(self) -> dict[str, Any] | None:
        return dict(self._last_analysis) if self._last_analysis else None
