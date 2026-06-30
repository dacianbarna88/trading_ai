"""Sector intelligence SSOT context — read-only from existing artifacts."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SECTOR_COLUMNS = (
    "Sector_Runtime_Score",
    "Sector_Runtime_Confidence",
    "Sector_Momentum",
    "Sector_Flow",
    "Sector_History",
)

ARTIFACT_FILES = {
    "sector_rotation": "sector_rotation.csv",
    "sector_history": "sector_rotation_history.csv",
    "sector_flow": "sector_flow_summary.txt",
    "sector_momentum": "sector_momentum_summary.txt",
    "sector_summary": "sector_intelligence_summary.txt",
    "sector_runtime": "tae_sector_runtime.json",
}


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


@dataclass
class SectorContext:
    ticker_to_sector: dict[str, str] = field(default_factory=dict)
    sector_scores: dict[str, float] = field(default_factory=dict)
    sector_momentum: dict[str, str] = field(default_factory=dict)
    sector_flow: dict[str, str] = field(default_factory=dict)
    history_rows: int = 0
    global_sector_score: float | None = None
    global_sector_confidence: float | None = None
    top_sector: str | None = None
    artifacts_loaded: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path | str = ".") -> SectorContext:
        root = Path(root)
        artifacts_loaded = {key: (root / name).is_file() for key, name in ARTIFACT_FILES.items()}

        rotation_rows = _read_csv_rows(root / ARTIFACT_FILES["sector_rotation"])
        ticker_to_sector: dict[str, str] = {}
        sector_scores: dict[str, float] = {}
        for row in rotation_rows:
            sector = str(row.get("Sector") or "").upper()
            ticker = str(row.get("Ticker") or "").upper()
            score = _parse_float(row.get("Sector_Score")) or 0.0
            if sector:
                sector_scores[sector] = max(sector_scores.get(sector, 0.0), score)
            if ticker and sector:
                ticker_to_sector[ticker] = sector

        history_rows = 0
        hist_path = root / ARTIFACT_FILES["sector_history"]
        if hist_path.is_file():
            history_rows = len(_read_csv_rows(hist_path))

        momentum_text = _read_text(root / ARTIFACT_FILES["sector_momentum"])
        sector_momentum: dict[str, str] = {}
        for line in momentum_text.splitlines():
            if "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3 and parts[0] and not parts[0].startswith("="):
                sector_momentum[parts[0].upper()] = parts[-1]

        flow_text = _read_text(root / ARTIFACT_FILES["sector_flow"])
        sector_flow: dict[str, str] = {}
        for line in flow_text.splitlines():
            if "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3 and parts[0] and not parts[0].startswith("="):
                sector_flow[parts[0].upper()] = parts[-1]

        top_sector = None
        if sector_scores:
            top_sector = max(sector_scores.items(), key=lambda x: x[1])[0]
            global_score = round(max(sector_scores.values()), 2)
        else:
            global_score = 55.0

        confidence = 55.0
        if history_rows >= 30:
            confidence = 80.0
        elif history_rows >= 10:
            confidence = 70.0
        elif history_rows >= 3:
            confidence = 62.0
        if artifacts_loaded.get("sector_summary"):
            confidence = min(100.0, confidence + 5.0)

        return cls(
            ticker_to_sector=ticker_to_sector,
            sector_scores=sector_scores,
            sector_momentum=sector_momentum,
            sector_flow=sector_flow,
            history_rows=history_rows,
            global_sector_score=global_score,
            global_sector_confidence=confidence,
            top_sector=top_sector,
            artifacts_loaded=artifacts_loaded,
        )

    def _sector_for_ticker(self, ticker: str) -> str | None:
        ticker = ticker.upper()
        if ticker in self.ticker_to_sector:
            return self.ticker_to_sector[ticker]
        for etf, sector in self.ticker_to_sector.items():
            if etf == ticker:
                return sector
        return self.top_sector

    def compute_bonuses(self, enrichment: dict[str, Any]) -> dict[str, float]:
        sector_score = _parse_float(enrichment.get("Sector_Runtime_Score"))
        sector_conf = _parse_float(enrichment.get("Sector_Runtime_Confidence"))
        momentum = str(enrichment.get("Sector_Momentum") or "")
        flow = str(enrichment.get("Sector_Flow") or "")

        sector_bonus = 0.0
        if sector_score is not None and sector_score >= 55:
            sector_bonus += (sector_score - 50) * 0.012
        if sector_conf is not None and sector_conf >= 65:
            sector_bonus += (sector_conf - 50) * 0.01
        if "ACCELERATING" in momentum:
            sector_bonus += 0.35
        elif "DECELERATING" in momentum:
            sector_bonus -= 0.2
        if "CAPITAL_FLOW_IN" in flow:
            sector_bonus += 0.25
        elif "CAPITAL_FLOW_OUT" in flow:
            sector_bonus -= 0.15

        return {"sector_bonus": round(sector_bonus, 4)}

    def enrich_ticker(self, ticker: str, *, signal: str = "") -> dict[str, Any]:
        ticker = ticker.upper()
        sector = self._sector_for_ticker(ticker)
        score = self.global_sector_score
        if sector and sector in self.sector_scores:
            score = self.sector_scores[sector]
        conf = self.global_sector_confidence
        momentum = self.sector_momentum.get(sector or "", "UNKNOWN")
        flow = self.sector_flow.get(sector or "", "UNKNOWN")
        history = f"rows={self.history_rows}; sector={sector or 'UNKNOWN'}"

        if str(signal or "").upper() == "STRONG BUY" and "ACCELERATING" in momentum:
            score = round(min(100.0, (score or 55) + 3.0), 2) if score is not None else 58.0

        enrichment = {
            "Sector_Runtime_Score": score,
            "Sector_Runtime_Confidence": conf,
            "Sector_Momentum": momentum,
            "Sector_Flow": flow,
            "Sector_History": history,
        }
        enrichment.update(self.compute_bonuses(enrichment))
        return enrichment

    def advisory_summary(self) -> dict[str, Any]:
        top_sectors = sorted(
            self.sector_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]
        return {
            "top_sector": self.top_sector,
            "sector_score": self.global_sector_score,
            "sector_confidence": self.global_sector_confidence,
            "history_rows": self.history_rows,
            "top_sectors": [{"sector": s, "score": sc} for s, sc in top_sectors],
            "artifacts_loaded": self.artifacts_loaded,
        }
