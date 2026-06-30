"""
Live signals historical intelligence enricher — read-only context from TAE artifacts.
"""

from __future__ import annotations

import csv
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ENRICHMENT_COLUMNS = (
    "Historical_Win_Rate",
    "Historical_Avg_Return",
    "Historical_Sharpe",
    "Strategy_Rank",
    "Strategy_Confidence",
    "Committee_Score",
    "Historical_Confidence",
    "Historical_Edge",
    "Recommendation_Context",
)

ARTIFACT_FILES = {
    "historical": "tae_historical_results_analysis.json",
    "strategic": "tae_strategic_performance_audit.json",
    "ranking": "tae_continuous_strategy_ranking.json",
    "registry": "tae_candidate_strategy_registry.json",
}


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
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


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _portfolio_ticker_stats(portfolio_path: Path) -> dict[str, dict[str, float]]:
    if not portfolio_path.is_file():
        return {}
    holdings: dict[str, float] = {}
    buy_lots: dict[str, list[tuple[float, float]]] = {}
    closed_pnls: dict[str, list[float]] = {}

    with portfolio_path.open(encoding="utf-8", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle):
            ticker = str(row.get("Ticker") or "").upper().strip()
            if not ticker or ticker == "CASH":
                continue
            action = str(row.get("Action") or "").upper()
            shares = _parse_float(row.get("Shares")) or 0.0
            price = _parse_float(row.get("Price")) or 0.0
            pnl_pct = _parse_float(row.get("PnL_%"))

            if action == "BUY":
                holdings[ticker] = holdings.get(ticker, 0.0) + shares
                buy_lots.setdefault(ticker, []).append((price, shares))
            elif action == "SELL":
                holdings[ticker] = holdings.get(ticker, 0.0) - shares
                if pnl_pct is not None:
                    closed_pnls.setdefault(ticker, []).append(pnl_pct)

    stats: dict[str, dict[str, float]] = {}
    for ticker, pnls in closed_pnls.items():
        wins = sum(1 for p in pnls if p > 0)
        stats[ticker] = {
            "win_rate": round(100.0 * wins / len(pnls), 2),
            "avg_return": round(sum(pnls) / len(pnls), 2),
            "trade_count": float(len(pnls)),
        }
    return stats


@dataclass
class HistoricalContext:
    historical: dict[str, Any] | None
    strategic: dict[str, Any] | None
    ranking: dict[str, Any] | None
    registry: dict[str, Any] | None
    portfolio_stats: dict[str, dict[str, float]]
    top_ranking: dict[str, Any] | None
    top_registry: dict[str, Any] | None
    market_medians: dict[str, dict[str, float | None]]
    global_median_sharpe: float | None
    global_median_return: float | None
    audit_win_rate: float | None

    @classmethod
    def load(cls, root: Path | str = ".") -> HistoricalContext:
        root = Path(root)
        historical = _load_json(root / ARTIFACT_FILES["historical"])
        strategic = _load_json(root / ARTIFACT_FILES["strategic"])
        ranking = _load_json(root / ARTIFACT_FILES["ranking"])
        registry = _load_json(root / ARTIFACT_FILES["registry"])
        portfolio_stats = _portfolio_ticker_stats(root / "portfolio.csv")

        rankings = list((ranking or {}).get("rankings") or [])
        top_ranking = rankings[0] if rankings else None

        top_registry = None
        if registry and top_ranking:
            top_id = top_ranking.get("candidate_id")
            for cand in registry.get("candidates") or []:
                if cand.get("candidate_id") == top_id:
                    top_registry = cand
                    break

        market_medians: dict[str, dict[str, float | None]] = {}
        top_per_market = (historical or {}).get("top_10_per_market") or {}
        for market, rows in top_per_market.items():
            if not isinstance(rows, list):
                continue
            sharpes = [_parse_float(r.get("sharpe")) for r in rows if isinstance(r, dict)]
            returns = [_parse_float(r.get("profit_pct")) for r in rows if isinstance(r, dict)]
            sharpes = [v for v in sharpes if v is not None]
            returns = [v for v in returns if v is not None]
            market_medians[str(market).upper()] = {
                "sharpe": _median(sharpes),
                "return": _median(returns),
            }

        robust = list((historical or {}).get("robust_strategy_shortlist") or [])
        robust_sharpes = [
            v
            for item in robust
            if isinstance(item, dict)
            for v in [_parse_float(item.get("avg_sharpe"))]
            if v is not None
        ]
        robust_returns = [
            v
            for item in robust
            if isinstance(item, dict)
            for v in [_parse_float(item.get("avg_profit_pct"))]
            if v is not None
        ]

        audit_win_rate = _parse_float(
            ((strategic or {}).get("trade_quality") or {}).get("win_rate")
        )

        return cls(
            historical=historical,
            strategic=strategic,
            ranking=ranking,
            registry=registry,
            portfolio_stats=portfolio_stats,
            top_ranking=top_ranking,
            top_registry=top_registry,
            market_medians=market_medians,
            global_median_sharpe=_median(robust_sharpes),
            global_median_return=_median(robust_returns),
            audit_win_rate=audit_win_rate,
        )

    def enrich_ticker(self, ticker: str, signal: str = "", score: Any = None) -> dict[str, Any]:
        ticker = str(ticker).upper().strip()
        market = _infer_market(ticker)
        market_stats = self.market_medians.get(market, {})

        port = self.portfolio_stats.get(ticker, {})
        hist_sharpe = market_stats.get("sharpe") or self.global_median_sharpe
        hist_return = market_stats.get("return") or self.global_median_return

        win_rate = port.get("win_rate")
        if win_rate is None and self.top_ranking:
            win_rate = _parse_float(self.top_ranking.get("win_rate"))
        if win_rate is None:
            win_rate = self.audit_win_rate

        strategy_rank = None
        strategy_confidence = None
        if self.top_ranking:
            strategy_rank = self.top_ranking.get("rank")
            strategy_confidence = _parse_float(self.top_ranking.get("ranking_score"))

        if win_rate is not None and strategy_confidence is not None:
            committee_score = round(win_rate * 0.4 + strategy_confidence * 100 * 0.6, 2)
        elif win_rate is not None:
            committee_score = round(win_rate, 2)
        elif strategy_confidence is not None:
            committee_score = round(strategy_confidence * 100, 2)
        else:
            committee_score = None

        sources = 0
        if self.historical:
            sources += 1
        if self.ranking:
            sources += 1
        if self.registry:
            sources += 1
        if port:
            sources += 1
        historical_confidence = round(min(100.0, 25.0 * sources + (10 if market_stats else 0)), 1)

        edge = "NEUTRAL"
        if hist_sharpe is not None and win_rate is not None:
            if hist_sharpe >= 0.5 and win_rate >= 50:
                edge = "POSITIVE"
            elif hist_sharpe < 0.2 or win_rate < 35:
                edge = "WEAK"
        elif hist_sharpe is not None and hist_sharpe >= 0.5:
            edge = "POSITIVE"

        strategy_id = (self.top_ranking or {}).get("candidate_id", "N/A")
        ctx_parts = [
            f"market={market}",
            f"edge={edge}",
            f"hist_sharpe={hist_sharpe:.2f}" if hist_sharpe is not None else "hist_sharpe=N/A",
            f"win_rate={win_rate:.1f}%" if win_rate is not None else "win_rate=N/A",
            f"strategy={strategy_id}",
            f"signal={signal or 'N/A'}",
        ]
        if score is not None:
            ctx_parts.append(f"score={score}")

        return {
            "Historical_Win_Rate": win_rate,
            "Historical_Avg_Return": hist_return,
            "Historical_Sharpe": round(hist_sharpe, 4) if hist_sharpe is not None else None,
            "Strategy_Rank": strategy_rank,
            "Strategy_Confidence": round(strategy_confidence, 4)
            if strategy_confidence is not None
            else None,
            "Committee_Score": committee_score,
            "Historical_Confidence": historical_confidence,
            "Historical_Edge": edge,
            "Recommendation_Context": "; ".join(ctx_parts),
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

    ctx = HistoricalContext.load(root)
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return {"ok": False, "error": "Empty live_signals.csv", "rows": 0}

    fieldnames = list(rows[0].keys())
    for col in ENRICHMENT_COLUMNS:
        if col not in fieldnames:
            fieldnames.append(col)

    enriched_count = 0
    for row in rows:
        ticker = str(row.get("Ticker") or "").upper()
        enrichment = ctx.enrich_ticker(
            ticker,
            signal=str(row.get("Signal") or ""),
            score=row.get("Score"),
        )
        row.update(enrichment)
        enriched_count += 1

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    strong_buy = sum(1 for r in rows if str(r.get("Signal", "")).upper() == "STRONG BUY")
    return {
        "ok": True,
        "rows": len(rows),
        "enriched": enriched_count,
        "strong_buy_count": strong_buy,
        "artifacts_loaded": {
            name: (root / fname).is_file()
            for name, fname in ARTIFACT_FILES.items()
        },
        "top_strategy": (ctx.top_ranking or {}).get("candidate_id"),
    }
