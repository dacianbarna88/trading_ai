"""Counterfactual + event memory + shadow SSOT context — read-only from existing artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

COUNTERFACTUAL_COLUMNS = (
    "Event_Memory_Score",
    "Event_Memory_Confidence",
    "Counterfactual_Score",
    "Counterfactual_Confidence",
    "Entry_Quality",
    "Exit_Quality",
    "Shadow_Validation",
    "Outcome_Memory",
    "Expected_Alternative_Return",
    "Counterfactual_Context",
)

ARTIFACT_FILES = {
    "event_memory": "tae_event_memory.json",
    "entry_cf": "tae_entry_counterfactual.json",
    "exit_cf": "tae_exit_counterfactual.json",
    "shadow_summary": "tae_shadow_validation_summary.json",
    "event_memory_runtime": "tae_event_memory_runtime.json",
    "counterfactual_runtime": "tae_counterfactual_runtime.json",
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


def _verdict_score(verdict: str, ok_values: tuple[str, ...]) -> float:
    v = str(verdict or "").upper()
    if any(ok in v for ok in ok_values):
        return 75.0
    if "OK" in v or "READY" in v:
        return 70.0
    if "WEAK" in v or "STRICT" in v:
        return 45.0
    return 55.0


@dataclass
class CounterfactualContext:
    event_memory: dict[str, Any] = field(default_factory=dict)
    entry_cf: dict[str, Any] = field(default_factory=dict)
    exit_cf: dict[str, Any] = field(default_factory=dict)
    shadow_summary: dict[str, Any] = field(default_factory=dict)
    entry_by_ticker: dict[str, dict[str, Any]] = field(default_factory=dict)
    exit_by_ticker: dict[str, dict[str, Any]] = field(default_factory=dict)
    shadow_by_ticker: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    global_event_score: float | None = None
    global_event_confidence: float | None = None
    global_cf_score: float | None = None
    global_cf_confidence: float | None = None
    global_alt_return: float | None = None
    artifacts_loaded: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path | str = ".") -> CounterfactualContext:
        root = Path(root)
        artifacts_loaded = {key: (root / name).is_file() for key, name in ARTIFACT_FILES.items()}

        event_memory = _load_json(root / ARTIFACT_FILES["event_memory"]) or {}
        entry_cf = _load_json(root / ARTIFACT_FILES["entry_cf"]) or {}
        exit_cf = _load_json(root / ARTIFACT_FILES["exit_cf"]) or {}
        shadow_summary = _load_json(root / ARTIFACT_FILES["shadow_summary"]) or {}

        entry_by_ticker: dict[str, dict[str, Any]] = {}
        for buy in entry_cf.get("buys") or []:
            ticker = str(buy.get("ticker") or "").upper()
            if ticker:
                entry_by_ticker[ticker] = buy

        exit_by_ticker: dict[str, dict[str, Any]] = {}
        for item in exit_cf.get("by_ticker") or []:
            ticker = str(item.get("bucket") or item.get("ticker") or "").upper()
            if ticker:
                exit_by_ticker[ticker] = item

        shadow_by_ticker: dict[str, list[dict[str, Any]]] = {}
        for event in shadow_summary.get("latest_20_events") or []:
            ticker = str(event.get("ticker") or "").upper()
            if ticker:
                shadow_by_ticker.setdefault(ticker, []).append(event)

        event_score = 70.0
        if event_memory.get("schema_validation_passed"):
            event_score += 15.0
        if event_memory.get("round_trip_passed"):
            event_score += 10.0
        event_count = _parse_float(event_memory.get("event_count")) or 0.0
        if event_count > 0:
            event_score = min(100.0, event_score + min(5.0, event_count))

        entry_verdict = str(entry_cf.get("verdict") or "")
        exit_verdict = str(exit_cf.get("verdict") or "")
        entry_score = _verdict_score(
            entry_verdict,
            ("APPROXIMATELY_OK", "ENTRY_LOGIC_APPROXIMATELY_OK"),
        )
        exit_score = _verdict_score(exit_verdict, ("APPROXIMATELY_OK", "EXIT_LOGIC_APPROXIMATELY_OK"))
        global_cf_score = round((entry_score + exit_score) / 2.0, 2)

        baseline = entry_cf.get("baseline") or {}
        win_rate = _parse_float(baseline.get("win_rate"))
        global_cf_confidence = win_rate if win_rate is not None else 60.0

        best_id = entry_cf.get("best_scenario_id")
        alt_return = None
        for scenario in entry_cf.get("scenarios") or []:
            if scenario.get("scenario_id") == best_id:
                alt_return = _parse_float(scenario.get("delta_vs_baseline"))
                break

        shadow_conf = _parse_float(shadow_summary.get("average_advisory_confidence"))
        if shadow_conf is None and shadow_summary.get("total_events"):
            block_rate = _parse_float(shadow_summary.get("block_rate")) or 0.0
            shadow_conf = round(max(40.0, 100.0 - block_rate * 100.0), 2)

        return cls(
            event_memory=event_memory,
            entry_cf=entry_cf,
            exit_cf=exit_cf,
            shadow_summary=shadow_summary,
            entry_by_ticker=entry_by_ticker,
            exit_by_ticker=exit_by_ticker,
            shadow_by_ticker=shadow_by_ticker,
            global_event_score=round(min(100.0, event_score), 2),
            global_event_confidence=100.0 if event_memory.get("round_trip_passed") else 70.0,
            global_cf_score=global_cf_score,
            global_cf_confidence=global_cf_confidence,
            global_alt_return=alt_return,
            artifacts_loaded=artifacts_loaded,
        )

    def _entry_quality(self, ticker: str) -> float | None:
        buy = self.entry_by_ticker.get(ticker)
        if buy:
            score = _parse_float(buy.get("score"))
            if score is not None:
                return round(score, 2)
            pnl = _parse_float(buy.get("total_pnl"))
            if pnl is not None:
                return round(max(0.0, min(100.0, 50.0 + pnl / 10.0)), 2)
        return None

    def _exit_quality(self, ticker: str) -> float | None:
        item = self.exit_by_ticker.get(ticker)
        if item:
            avg_delta = _parse_float(item.get("avg_delta"))
            if avg_delta is not None:
                return round(max(0.0, min(100.0, 50.0 + avg_delta)), 2)
        return None

    def _shadow_status(self, ticker: str) -> str:
        events = self.shadow_by_ticker.get(ticker) or []
        if not events:
            total = int(self.shadow_summary.get("total_events") or 0)
            if total <= 0:
                return "NO_SHADOW_EVENTS"
            return "NO_TICKER_SHADOW"
        latest = events[-1]
        event_type = str(latest.get("event_type") or "")
        if "ALLOWED" in event_type:
            return "SHADOW_ALLOWED"
        if "BLOCKED" in event_type:
            return "SHADOW_BLOCKED"
        return event_type or "SHADOW_UNKNOWN"

    def _expected_alt_return(self, ticker: str) -> float | None:
        exit_item = self.exit_by_ticker.get(ticker)
        if exit_item:
            return _parse_float(exit_item.get("avg_delta"))
        return self.global_alt_return

    def compute_bonuses(self, enrichment: dict[str, Any]) -> dict[str, float]:
        event_score = _parse_float(enrichment.get("Event_Memory_Score"))
        event_conf = _parse_float(enrichment.get("Event_Memory_Confidence"))
        cf_score = _parse_float(enrichment.get("Counterfactual_Score"))
        cf_conf = _parse_float(enrichment.get("Counterfactual_Confidence"))
        entry_q = _parse_float(enrichment.get("Entry_Quality"))
        exit_q = _parse_float(enrichment.get("Exit_Quality"))
        shadow = str(enrichment.get("Shadow_Validation") or "")

        event_memory_bonus = 0.0
        if event_score is not None and event_score >= 65:
            event_memory_bonus += (event_score - 50) * 0.015
        if event_conf is not None and event_conf >= 75:
            event_memory_bonus += (event_conf - 50) * 0.01

        counterfactual_bonus = 0.0
        if cf_score is not None and cf_score >= 60:
            counterfactual_bonus += (cf_score - 50) * 0.02
        if cf_conf is not None and cf_conf >= 65:
            counterfactual_bonus += (cf_conf - 50) * 0.015

        entry_bonus = 0.0
        if entry_q is not None and entry_q >= 70:
            entry_bonus += (entry_q - 50) * 0.02

        exit_bonus = 0.0
        if exit_q is not None and exit_q >= 55:
            exit_bonus += (exit_q - 50) * 0.015

        shadow_bonus = 0.0
        if "ALLOWED" in shadow:
            shadow_bonus += 0.5
        elif "BLOCKED" in shadow:
            shadow_bonus -= 0.5

        return {
            "event_memory_bonus": round(event_memory_bonus, 4),
            "counterfactual_bonus": round(counterfactual_bonus, 4),
            "entry_bonus": round(entry_bonus, 4),
            "exit_bonus": round(exit_bonus, 4),
            "shadow_bonus": round(shadow_bonus, 4),
        }

    def enrich_ticker(self, ticker: str) -> dict[str, Any]:
        ticker = ticker.upper()
        entry_q = self._entry_quality(ticker)
        exit_q = self._exit_quality(ticker)
        if entry_q is None:
            entry_q = self.global_cf_score
        if exit_q is None:
            exit_q = self.global_cf_score

        cf_score = None
        if entry_q is not None and exit_q is not None:
            cf_score = round((entry_q + exit_q) / 2.0, 2)
        elif self.global_cf_score is not None:
            cf_score = self.global_cf_score

        shadow_status = self._shadow_status(ticker)
        outcome_memory = str(
            self.shadow_summary.get("outcome_tracking_status")
            or f"events={self.shadow_summary.get('total_events', 0)}"
        )
        alt_return = self._expected_alt_return(ticker)

        ctx_parts = [
            f"ticker={ticker}",
            f"entry={self.entry_cf.get('verdict')}",
            f"exit={self.exit_cf.get('verdict')}",
            f"entry_q={entry_q}",
            f"exit_q={exit_q}",
            f"shadow={shadow_status}",
            f"alt_return={alt_return}",
            f"event_verdict={self.event_memory.get('verdict')}",
        ]

        enrichment = {
            "Event_Memory_Score": self.global_event_score,
            "Event_Memory_Confidence": self.global_event_confidence,
            "Counterfactual_Score": cf_score,
            "Counterfactual_Confidence": self.global_cf_confidence,
            "Entry_Quality": entry_q,
            "Exit_Quality": exit_q,
            "Shadow_Validation": shadow_status,
            "Outcome_Memory": outcome_memory,
            "Expected_Alternative_Return": alt_return,
            "Counterfactual_Context": "; ".join(ctx_parts),
        }
        enrichment.update(self.compute_bonuses(enrichment))
        return enrichment

    def advisory_summary(self) -> dict[str, Any]:
        return {
            "event_memory_verdict": self.event_memory.get("verdict"),
            "event_count": self.event_memory.get("event_count"),
            "entry_verdict": self.entry_cf.get("verdict"),
            "exit_verdict": self.exit_cf.get("verdict"),
            "best_scenario_id": self.entry_cf.get("best_scenario_id"),
            "expected_alternative_return": self.global_alt_return,
            "shadow_total_events": self.shadow_summary.get("total_events"),
            "shadow_block_rate": self.shadow_summary.get("block_rate"),
            "outcome_memory": self.shadow_summary.get("outcome_tracking_status"),
            "top_entry_tickers": list(self.entry_by_ticker.keys())[:10],
            "top_exit_tickers": list(self.exit_by_ticker.keys())[:10],
            "artifacts_loaded": self.artifacts_loaded,
        }
