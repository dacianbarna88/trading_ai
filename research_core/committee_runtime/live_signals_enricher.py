"""
Live signals committee enricher — read-only context from existing committee artifacts.
"""

from __future__ import annotations

import csv
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

COMMITTEE_COLUMNS = (
    "Committee_Votes",
    "Committee_Weighted_Score",
    "Committee_Confidence",
    "Committee_Decision",
    "Committee_History",
    "Committee_Accuracy",
    "Committee_Adaptive_Weight",
    "Committee_Context",
)

ARTIFACT_FILES = {
    "strategic_summary": "strategic_committee_summary.txt",
    "weighted_decision": "weighted_committee_decision.txt",
    "weighted_summary": "weighted_committee_summary.txt",
    "confidence_breakdown": "committee_confidence_breakdown.txt",
    "vote_history": "vote_history.csv",
    "vote_accuracy": "vote_accuracy.csv",
    "adaptive_weights": "adaptive_weights.csv",
    "learning_weights": "learning_weight_history.csv",
    "confidence_evolution": "confidence_evolution_summary.txt",
}


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _extract_label(text: str, label: str) -> str | None:
    for line in text.splitlines():
        if line.startswith(label):
            return line.split(":", 1)[1].strip()
    return None


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
        return "US"


def _parse_weighted_decision(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "weighted_score": None,
        "confidence": None,
        "decision": None,
        "total_weight": None,
    }
    for line in text.splitlines():
        if line.startswith("Total Weighted Score:"):
            result["weighted_score"] = _parse_float(line.split(":", 1)[1])
        elif line.startswith("Total Weight:"):
            result["total_weight"] = _parse_float(line.split(":", 1)[1])
        elif line.startswith("Confidence:"):
            result["confidence"] = _parse_float(line.split(":", 1)[1])
        elif line.startswith("Final Decision:"):
            result["decision"] = line.split(":", 1)[1].strip()
    return result


def _latest_vote_history(rows: list[dict[str, str]]) -> tuple[str, dict[str, str]]:
    if not rows:
        return "", {}
    timestamps = sorted({str(r.get("Timestamp") or "") for r in rows if r.get("Timestamp")})
    latest = timestamps[-1] if timestamps else ""
    votes: dict[str, str] = {}
    for row in rows:
        if str(row.get("Timestamp") or "") == latest:
            votes[str(row.get("Vote") or "").upper()] = str(row.get("Decision") or "")
    return latest, votes


@dataclass
class CommitteeContext:
    latest_votes: dict[str, str]
    vote_history_ts: str
    weighted_score: float | None
    weighted_confidence: float | None
    committee_decision: str
    strategic_decision: str | None
    strategic_confidence: float | None
    committee_vote: str | None
    avg_accuracy: float | None
    avg_adaptive_weight: float | None
    adaptive_weights: dict[str, float]
    vote_accuracy: dict[str, float]
    consensus: str
    top_candidates: list[dict[str, Any]] = field(default_factory=list)
    artifacts_loaded: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path | str = ".") -> CommitteeContext:
        root = Path(root)
        artifacts_loaded = {
            name: (root / fname).is_file() for name, fname in ARTIFACT_FILES.items()
        }

        history_rows = _load_csv_rows(root / ARTIFACT_FILES["vote_history"])
        vote_history_ts, latest_votes = _latest_vote_history(history_rows)

        weighted_text = _read_text(root / ARTIFACT_FILES["weighted_decision"])
        if not weighted_text.strip():
            weighted_text = _read_text(root / ARTIFACT_FILES["weighted_summary"])
        weighted = _parse_weighted_decision(weighted_text)

        strategic_text = _read_text(root / ARTIFACT_FILES["strategic_summary"])
        strategic_decision = (
            _extract_label(strategic_text, "FINAL DECISION")
            or _extract_label(strategic_text, "Committee Vote")
        )
        strategic_confidence = _parse_float(_extract_label(strategic_text, "Confidence") or "")
        committee_vote = _extract_label(strategic_text, "Committee Vote")

        accuracy_rows = _load_csv_rows(root / ARTIFACT_FILES["vote_accuracy"])
        vote_accuracy: dict[str, float] = {}
        accuracies: list[float] = []
        for row in accuracy_rows:
            vote = str(row.get("Vote") or "").upper()
            acc = _parse_float(row.get("Accuracy_%"))
            if vote and acc is not None:
                vote_accuracy[vote] = acc
                if acc > 0:
                    accuracies.append(acc)
        avg_accuracy = round(statistics.mean(accuracies), 2) if accuracies else None

        weight_rows = _load_csv_rows(root / ARTIFACT_FILES["adaptive_weights"])
        adaptive_weights: dict[str, float] = {}
        weights: list[float] = []
        for row in weight_rows:
            vote = str(row.get("Vote") or "").upper()
            w = _parse_float(row.get("New_Weight") or row.get("Weight"))
            if vote and w is not None:
                adaptive_weights[vote] = w
                weights.append(w)
        avg_adaptive_weight = round(statistics.mean(weights), 3) if weights else None

        decision = weighted.get("decision") or committee_vote or strategic_decision or "WAIT"
        confidence = weighted.get("confidence") or strategic_confidence

        bullish = sum(
            1
            for v in latest_votes.values()
            if any(k in v.upper() for k in ("BULLISH", "BUY", "LONG_TERM", "ACCUMULATE"))
        )
        total_votes = len(latest_votes) or 1
        if bullish >= total_votes * 0.6:
            consensus = "BULLISH_CONSENSUS"
        elif bullish <= total_votes * 0.2:
            consensus = "BEARISH_CONSENSUS"
        else:
            consensus = "MIXED_CONSENSUS"

        return cls(
            latest_votes=latest_votes,
            vote_history_ts=vote_history_ts,
            weighted_score=weighted.get("weighted_score"),
            weighted_confidence=confidence,
            committee_decision=str(decision).upper(),
            strategic_decision=strategic_decision,
            strategic_confidence=strategic_confidence,
            committee_vote=committee_vote,
            avg_accuracy=avg_accuracy,
            avg_adaptive_weight=avg_adaptive_weight,
            adaptive_weights=adaptive_weights,
            vote_accuracy=vote_accuracy,
            consensus=consensus,
            artifacts_loaded=artifacts_loaded,
        )

    def _ticker_vote_alignment(self, ticker: str) -> float:
        market = _infer_market(ticker).upper()
        alignment = 0.0
        regional = self.latest_votes.get("REGIONAL", "")
        horizon = self.latest_votes.get("HORIZON", "")
        sector = self.latest_votes.get("SECTOR", "")

        if market == "US" and "US" in regional.upper():
            alignment += 1.0
        if market == "EU" and "EUROPE" in horizon.upper():
            alignment += 1.0
        if market == "UK" and "UK" in horizon.upper():
            alignment += 1.0
        if "TECH" in sector.upper() and ticker in {"NVDA", "AAPL", "MSFT", "QQQ"}:
            alignment += 0.5
        if self.committee_decision in {"BUY", "ACCUMULATE_US_TECH", "AGGRESSIVE", "NORMAL"}:
            alignment += 1.0
        elif self.committee_decision in {"SELL", "DEFENSIVE"}:
            alignment -= 1.0
        return alignment

    def enrich_ticker(self, ticker: str, signal: str = "", score: Any = None) -> dict[str, Any]:
        ticker = str(ticker).upper().strip()
        votes_str = "; ".join(f"{k}={v}" for k, v in sorted(self.latest_votes.items())) or "NO_VOTES"

        alignment = self._ticker_vote_alignment(ticker)
        base_conf = self.weighted_confidence or self.strategic_confidence or 50.0
        ticker_confidence = round(min(100.0, max(0.0, base_conf + alignment * 5)), 2)

        adaptive_weight = self.avg_adaptive_weight
        if self.adaptive_weights:
            dominant = max(self.adaptive_weights.items(), key=lambda x: x[1])
            adaptive_weight = round(
                (self.avg_adaptive_weight or dominant[1]) + alignment * 0.1,
                3,
            )

        accuracy = self.avg_accuracy
        if self.vote_accuracy:
            accuracy = round(
                statistics.mean(self.vote_accuracy.values()) if self.vote_accuracy else 0,
                2,
            )

        decision = self.committee_decision
        if signal.upper() == "STRONG BUY" and decision in {"BUY", "WAIT"} and alignment >= 1:
            decision = "BUY_ALIGNED"
        elif signal.upper() == "STRONG BUY" and decision in {"SELL", "DEFENSIVE"}:
            decision = "CONFLICT"

        ctx_parts = [
            f"decision={decision}",
            f"consensus={self.consensus}",
            f"weighted={self.weighted_score}",
            f"confidence={ticker_confidence}",
            f"accuracy={accuracy}",
            f"signal={signal or 'N/A'}",
        ]
        if score is not None:
            ctx_parts.append(f"score={score}")

        return {
            "Committee_Votes": votes_str,
            "Committee_Weighted_Score": self.weighted_score,
            "Committee_Confidence": ticker_confidence,
            "Committee_Decision": decision,
            "Committee_History": self.vote_history_ts or "NO_HISTORY",
            "Committee_Accuracy": accuracy,
            "Committee_Adaptive_Weight": adaptive_weight,
            "Committee_Context": "; ".join(ctx_parts),
        }

    def advisory_summary(self) -> dict[str, Any]:
        return {
            "committee_summary": (
                f"decision={self.committee_decision} consensus={self.consensus} "
                f"weighted_score={self.weighted_score} confidence={self.weighted_confidence}"
            ),
            "highest_confidence_candidates": [],
            "weighted_decisions": {
                "final_decision": self.committee_decision,
                "weighted_score": self.weighted_score,
                "confidence": self.weighted_confidence,
            },
            "committee_consensus": self.consensus,
            "committee_confidence": self.weighted_confidence,
            "vote_snapshot": self.latest_votes,
            "avg_accuracy": self.avg_accuracy,
            "avg_adaptive_weight": self.avg_adaptive_weight,
            "artifacts_loaded": self.artifacts_loaded,
        }


def enrich_live_signals_file(
    root: Path | str = ".",
    *,
    signals_path: str = "live_signals.csv",
) -> dict[str, Any]:
    root = Path(root)
    path = root / signals_path
    if not path.is_file():
        return {"ok": False, "error": f"Missing {signals_path}", "rows": 0}

    ctx = CommitteeContext.load(root)
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return {"ok": False, "error": "Empty live_signals.csv", "rows": 0}

    fieldnames = list(rows[0].keys())
    for col in COMMITTEE_COLUMNS:
        if col not in fieldnames:
            fieldnames.append(col)

    enriched = 0
    strong_buy_committee: list[dict[str, Any]] = []
    for row in rows:
        ticker = str(row.get("Ticker") or "").upper()
        enrichment = ctx.enrich_ticker(
            ticker,
            signal=str(row.get("Signal") or ""),
            score=row.get("Score"),
        )
        row.update(enrichment)
        enriched += 1
        if str(row.get("Signal", "")).upper() == "STRONG BUY":
            strong_buy_committee.append({"ticker": ticker, **enrichment})

    strong_buy_committee.sort(
        key=lambda x: _parse_float(x.get("Committee_Confidence")) or 0,
        reverse=True,
    )
    ctx.top_candidates = strong_buy_committee[:5]
    advisory = ctx.advisory_summary()
    advisory["highest_confidence_candidates"] = [
        {
            "ticker": c["ticker"],
            "confidence": c.get("Committee_Confidence"),
            "decision": c.get("Committee_Decision"),
        }
        for c in strong_buy_committee[:5]
    ]

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    strong_buy = sum(1 for r in rows if str(r.get("Signal", "")).upper() == "STRONG BUY")
    return {
        "ok": True,
        "rows": len(rows),
        "enriched": enriched,
        "strong_buy_count": strong_buy,
        "strong_buy_committee_summary": strong_buy_committee[:10],
        "advisory_summary": advisory,
        "artifacts_loaded": ctx.artifacts_loaded,
    }
