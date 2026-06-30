"""Strategy discovery/simulation SSOT context — read-only from existing artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STRATEGY_COLUMNS = (
    "Strategy_Discovery_Score",
    "Strategy_Discovery_Confidence",
    "Strategy_Discovery_Context",
    "Strategy_Simulation_Score",
    "Strategy_Simulation_Confidence",
    "Strategy_Simulation_Context",
    "Discovery_Strategy",
    "Simulation_Strategy",
    "Expected_Edge",
    "Expected_Return",
    "Expected_Drawdown",
)

ARTIFACT_FILES = {
    "discovery": "tae_strategy_discovery.json",
    "simulation": "tae_strategy_simulation.json",
    "historical_research": "tae_historical_research.json",
    "historical_execution": "tae_historical_execution.json",
    "historical_analysis": "tae_historical_results_analysis.json",
    "discovery_runtime": "tae_strategy_discovery_runtime.json",
    "simulation_runtime": "tae_strategy_simulation_runtime.json",
}


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _infer_market(ticker: str) -> str:
    try:
        from markets.market_hours import get_ticker_market

        return get_ticker_market(ticker)
    except Exception:
        ticker = ticker.upper()
        if ticker.endswith(".L"):
            return "UK"
        if ticker.endswith((".DE", ".PA", ".AS", ".MI", ".SW", ".MC", ".BR")):
            return "EU"
        if ticker.endswith((".HK", ".T", ".KS", ".SI")):
            return "ASIA"
        return "US"


def _market_match(candidate_market: str, ticker_market: str) -> bool:
    cm = str(candidate_market or "ALL").upper()
    if cm in {"ALL", "GLOBAL", "ANY"}:
        return True
    return cm == ticker_market.upper()


@dataclass
class StrategyContext:
    discovery_by_market: dict[str, dict[str, Any]] = field(default_factory=dict)
    simulation_by_market: dict[str, dict[str, Any]] = field(default_factory=dict)
    global_top_discovery: dict[str, Any] | None = None
    global_top_simulation: dict[str, Any] | None = None
    simulation_confidence: float | None = None
    discovery_avg_confidence: float | None = None
    artifacts_loaded: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path | str = ".") -> StrategyContext:
        root = Path(root)
        artifacts_loaded = {key: (root / name).is_file() for key, name in ARTIFACT_FILES.items()}

        discovery = _load_json(root / ARTIFACT_FILES["discovery"]) or {}
        simulation = _load_json(root / ARTIFACT_FILES["simulation"]) or {}
        analysis = _load_json(root / ARTIFACT_FILES["historical_analysis"]) or {}

        discovery_by_market: dict[str, dict[str, Any]] = {}
        registry = discovery.get("discovery_registry") or []
        sorted_discovery = sorted(
            registry,
            key=lambda x: _parse_float(x.get("confidence_seed")) or 0.0,
            reverse=True,
        )
        for item in sorted_discovery:
            market = str(item.get("market") or "ALL").upper()
            if market not in discovery_by_market:
                discovery_by_market[market] = item
            if "ALL" not in discovery_by_market:
                discovery_by_market["ALL"] = item

        simulation_by_market: dict[str, dict[str, Any]] = {}
        per_market = analysis.get("top_10_per_market") or {}
        for market, items in per_market.items():
            if items:
                simulation_by_market[str(market).upper()] = items[0]

        global_top = (analysis.get("top_20_global_results") or [{}])[0]
        if global_top:
            simulation_by_market.setdefault("ALL", global_top)

        jobs_total = _parse_float(analysis.get("jobs_total")) or 0.0
        jobs_completed = _parse_float(analysis.get("jobs_completed")) or 0.0
        simulation_confidence = None
        if jobs_total > 0:
            simulation_confidence = round(min(100.0, (jobs_completed / jobs_total) * 100.0), 2)

        avg_conf = _parse_float(discovery.get("average_confidence_seed"))
        discovery_avg_confidence = round(avg_conf * 100, 2) if avg_conf is not None else None

        return cls(
            discovery_by_market=discovery_by_market,
            simulation_by_market=simulation_by_market,
            global_top_discovery=sorted_discovery[0] if sorted_discovery else None,
            global_top_simulation=global_top if global_top else None,
            simulation_confidence=simulation_confidence,
            discovery_avg_confidence=discovery_avg_confidence,
            artifacts_loaded=artifacts_loaded,
        )

    def _pick_discovery(self, market: str) -> dict[str, Any] | None:
        if market in self.discovery_by_market:
            return self.discovery_by_market[market]
        if "ALL" in self.discovery_by_market:
            return self.discovery_by_market["ALL"]
        return self.global_top_discovery

    def _pick_simulation(self, market: str) -> dict[str, Any] | None:
        if market in self.simulation_by_market:
            return self.simulation_by_market[market]
        if "ALL" in self.simulation_by_market:
            return self.simulation_by_market["ALL"]
        return self.global_top_simulation

    def compute_discovery_bonus(self, discovery_score: float | None, discovery_conf: float | None) -> float:
        bonus = 0.0
        if discovery_score is not None and discovery_score >= 60:
            bonus += (discovery_score - 50) * 0.02
        if discovery_conf is not None and discovery_conf >= 65:
            bonus += (discovery_conf - 50) * 0.015
        return round(bonus, 4)

    def compute_simulation_bonus(self, simulation_score: float | None, simulation_conf: float | None) -> float:
        bonus = 0.0
        if simulation_score is not None and simulation_score >= 55:
            bonus += (simulation_score - 50) * 0.025
        if simulation_conf is not None and simulation_conf >= 70:
            bonus += (simulation_conf - 50) * 0.015
        return round(bonus, 4)

    def enrich_ticker(self, ticker: str, market: str | None = None) -> dict[str, Any]:
        market = (market or _infer_market(ticker)).upper()
        discovery = self._pick_discovery(market)
        simulation = self._pick_simulation(market)

        if discovery and not _market_match(str(discovery.get("market") or "ALL"), market):
            discovery = self._pick_discovery("ALL")

        disc_conf_seed = _parse_float((discovery or {}).get("confidence_seed"))
        discovery_score = round(disc_conf_seed * 100, 2) if disc_conf_seed is not None else None
        discovery_confidence = discovery_score

        composite = _parse_float((simulation or {}).get("composite_score"))
        simulation_score = composite
        if simulation_score is not None and simulation_score <= 100:
            pass
        elif composite is not None:
            simulation_score = round(min(100.0, composite), 2)

        simulation_confidence = self.simulation_confidence
        expected_return = _parse_float((simulation or {}).get("profit_pct"))
        expected_drawdown = _parse_float((simulation or {}).get("max_drawdown"))
        expected_edge = _parse_float((simulation or {}).get("expectancy"))
        if expected_edge is None:
            expected_edge = composite

        discovery_id = (discovery or {}).get("discovery_id")
        simulation_id = (simulation or {}).get("strategy_id")

        ctx_parts = [
            f"market={market}",
            f"discovery={discovery_id}",
            f"simulation={simulation_id}",
            f"disc_score={discovery_score}",
            f"sim_score={simulation_score}",
            f"expected_return={expected_return}",
            f"expected_edge={expected_edge}",
        ]

        enrichment = {
            "Strategy_Discovery_Score": discovery_score,
            "Strategy_Discovery_Confidence": discovery_confidence,
            "Strategy_Discovery_Context": "; ".join(ctx_parts),
            "Strategy_Simulation_Score": simulation_score,
            "Strategy_Simulation_Confidence": simulation_confidence,
            "Strategy_Simulation_Context": (
                f"strategy={simulation_id}; composite={composite}; "
                f"return={expected_return}; drawdown={expected_drawdown}; edge={expected_edge}"
            ),
            "Discovery_Strategy": discovery_id,
            "Simulation_Strategy": simulation_id,
            "Expected_Edge": expected_edge,
            "Expected_Return": expected_return,
            "Expected_Drawdown": expected_drawdown,
            "strategy_discovery_bonus": self.compute_discovery_bonus(discovery_score, discovery_confidence),
            "strategy_simulation_bonus": self.compute_simulation_bonus(simulation_score, simulation_confidence),
        }
        return enrichment

    def advisory_summary(self) -> dict[str, Any]:
        top_discovered = []
        for market, item in sorted(self.discovery_by_market.items()):
            if market == "ALL":
                continue
            top_discovered.append(
                {
                    "discovery_id": item.get("discovery_id"),
                    "market": market,
                    "confidence_seed": item.get("confidence_seed"),
                }
            )
        top_discovered.sort(
            key=lambda x: _parse_float(x.get("confidence_seed")) or 0,
            reverse=True,
        )

        top_simulated = []
        for market, item in sorted(self.simulation_by_market.items()):
            if market == "ALL":
                continue
            top_simulated.append(
                {
                    "strategy_id": item.get("strategy_id"),
                    "market": market,
                    "composite_score": item.get("composite_score"),
                    "profit_pct": item.get("profit_pct"),
                    "expectancy": item.get("expectancy"),
                    "max_drawdown": item.get("max_drawdown"),
                }
            )
        top_simulated.sort(
            key=lambda x: _parse_float(x.get("composite_score")) or 0,
            reverse=True,
        )

        return {
            "discovery_avg_confidence": self.discovery_avg_confidence,
            "simulation_confidence": self.simulation_confidence,
            "top_discovered_strategies": top_discovered[:10],
            "top_simulated_strategies": top_simulated[:10],
            "artifacts_loaded": self.artifacts_loaded,
        }
