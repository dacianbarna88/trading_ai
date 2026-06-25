"""Regime-aware trust — trust profiles across market contexts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TrustRegime(str, Enum):
    GLOBAL = "GLOBAL"
    BULL = "BULL"
    BEAR = "BEAR"
    NEUTRAL = "NEUTRAL"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"


@dataclass
class RegimeTrustEvent:
    organism_name: str
    regime: TrustRegime
    delta: float
    reason: str
    trust_after: float
    timestamp: datetime


class RegimeAwareTrust:
    """
    Multi-dimensional trust beyond a single scalar.
    Organism reliability varies by regime and volatility context.
    """

    DEFAULT_TRUST: float = 50.0
    REGIMES: tuple[TrustRegime, ...] = tuple(TrustRegime)

    def __init__(self) -> None:
        self._trust: dict[str, dict[TrustRegime, float]] = {}
        self._history: list[RegimeTrustEvent] = []

    def register(self, organism_name: str, initial: float | None = None) -> dict[TrustRegime, float]:
        level = initial if initial is not None else self.DEFAULT_TRUST
        profile: dict[TrustRegime, float] = {}
        for regime in self.REGIMES:
            profile[regime] = max(0.0, min(100.0, level))
        self._trust[organism_name] = profile
        return dict(profile)

    def update_trust(
        self,
        organism: str,
        regime: TrustRegime | str,
        delta: float,
        reason: str = "",
    ) -> float:
        regime_key = TrustRegime(regime) if isinstance(regime, str) else regime
        if organism not in self._trust:
            self.register(organism)
        current = self._trust[organism][regime_key]
        new_level = max(0.0, min(100.0, current + delta))
        self._trust[organism][regime_key] = new_level
        self._history.append(
            RegimeTrustEvent(
                organism_name=organism,
                regime=regime_key,
                delta=delta,
                reason=reason,
                trust_after=new_level,
                timestamp=datetime.now(timezone.utc),
            )
        )
        global_level = self._trust[organism][TrustRegime.GLOBAL]
        blended = max(0.0, min(100.0, global_level + delta * 0.5))
        self._trust[organism][TrustRegime.GLOBAL] = blended
        return new_level

    def current_trust(self, organism: str, regime: TrustRegime | str) -> float:
        regime_key = TrustRegime(regime) if isinstance(regime, str) else regime
        if organism not in self._trust:
            self.register(organism)
        return self._trust[organism][regime_key]

    def trust_profile(self, organism: str) -> dict[str, float]:
        if organism not in self._trust:
            self.register(organism)
        return {r.value: round(v, 2) for r, v in self._trust[organism].items()}

    def all_profiles(self) -> dict[str, dict[str, float]]:
        return {name: self.trust_profile(name) for name in self._trust}

    def regime_statistics(self) -> dict[str, Any]:
        stats: dict[str, dict[str, float]] = {}
        for regime in self.REGIMES:
            values = [
                profile[regime]
                for profile in self._trust.values()
            ]
            if not values:
                stats[regime.value] = {"count": 0, "mean": 0.0, "min": 0.0, "max": 0.0}
            else:
                stats[regime.value] = {
                    "count": len(values),
                    "mean": round(sum(values) / len(values), 2),
                    "min": round(min(values), 2),
                    "max": round(max(values), 2),
                }
        return stats

    def history(self, organism: str | None = None) -> list[RegimeTrustEvent]:
        if organism is None:
            return list(self._history)
        return [e for e in self._history if e.organism_name == organism]

    def infer_regime_from_features(self, features: dict[str, Any]) -> TrustRegime:
        regime_label = str(features.get("regime", features.get("market_regime", "NEUTRAL"))).upper()
        if "BEAR" in regime_label:
            base = TrustRegime.BEAR
        elif "BULL" in regime_label:
            base = TrustRegime.BULL
        else:
            base = TrustRegime.NEUTRAL

        volatility = features.get("volatility_regime", features.get("atr_regime", ""))
        vol_str = str(volatility).upper()
        if "HIGH" in vol_str or features.get("high_volatility"):
            return TrustRegime.HIGH_VOLATILITY
        if "LOW" in vol_str or features.get("low_volatility"):
            return TrustRegime.LOW_VOLATILITY
        return base
