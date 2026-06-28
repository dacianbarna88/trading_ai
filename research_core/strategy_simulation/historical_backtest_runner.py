"""
Historical backtest runner — Phase X Sprint X.4

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE

Executes discovery strategy rules against real OHLCV history via MarketDataService.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from daily_gainers_strategy_research import build_ticker_universe, load_tickers_from_file
from research_core.config.base import BaseResearchConfig
from research_core.hypothesis.experiment_runner import ResearchDataLoader
from research_core.services.market_data import MarketDataService

logger = logging.getLogger(__name__)

MIN_TRADES_FOR_METRICS = 3
MAX_TICKERS_PER_MARKET = 5

HORIZON_PERIOD: dict[str, str] = {
    "2Y": "2y",
    "5Y": "5y",
    "10Y": "10y",
    "20Y": "max",
}

MARKET_PROXY_TICKERS: dict[str, list[str]] = {
    "US": ["SPY"],
    "EU": ["FEZ"],
    "UK": ["EWU"],
    "ASIA": ["EWJ", "FXI"],
}

WATCHLIST_FILES: dict[str, str] = {
    "US": "watchlist_us.txt",
    "EU": "watchlist_eu.txt",
    "UK": "watchlist_uk.txt",
}


@dataclass
class DataAvailability:
    available: bool
    ohlcv_available: bool
    csv_available: bool
    block_reason: str | None = None
    ohlcv_probe_ticker: str = "SPY"
    ohlcv_probe_rows: int = 0
    csv_row_count: int = 0


@dataclass
class BacktestOutcome:
    status: str
    metrics: dict[str, float] | None = None
    block_reason: str | None = None
    trade_count: int = 0
    tickers_used: list[str] = field(default_factory=list)
    data_source: str = "ohlcv"


def check_data_availability(root: Path) -> DataAvailability:
    config = BaseResearchConfig()
    service = MarketDataService(config)
    spy = service.download("SPY")
    ohlcv_ok = not spy.empty and len(spy) >= 100

    csv_loader = ResearchDataLoader()
    csv_ok = csv_loader.load()

    if ohlcv_ok:
        return DataAvailability(
            available=True,
            ohlcv_available=True,
            csv_available=csv_ok,
            ohlcv_probe_rows=len(spy),
        )

    if csv_ok:
        return DataAvailability(
            available=True,
            ohlcv_available=False,
            csv_available=True,
            csv_row_count=csv_loader.row_count,
            block_reason="OHLCV unavailable; CSV cohort fallback only for limited jobs.",
        )

    return DataAvailability(
        available=False,
        ohlcv_available=False,
        csv_available=False,
        block_reason="No OHLCV history and no research CSV data available.",
    )


def resolve_market_tickers(market: str, root: Path) -> list[str]:
    tickers: list[str] = []
    watchlist = WATCHLIST_FILES.get(market)
    if watchlist:
        tickers.extend(load_tickers_from_file(root / watchlist))

    if market == "US":
        tickers.extend(load_tickers_from_file(root / "us_expanded_universe.txt"))

    region_map = build_ticker_universe()
    for ticker, region in region_map.items():
        if region == market and market in {"US", "EU", "UK"}:
            tickers.append(ticker)

    tickers.extend(MARKET_PROXY_TICKERS.get(market, []))

    deduped: list[str] = []
    seen: set[str] = set()
    for ticker in tickers:
        upper = ticker.strip().upper()
        if upper and upper not in seen:
            seen.add(upper)
            deduped.append(upper)

    return deduped[:MAX_TICKERS_PER_MARKET] if deduped else list(MARKET_PROXY_TICKERS.get(market, ["SPY"]))


def _parse_entry_features(entry_rule: str) -> list[str]:
    return [part.strip() for part in entry_rule.split("+") if part.strip()]


def _entry_feature_passes(feature: str, row: pd.Series, prev: pd.Series) -> bool:
    if feature == "RSI":
        rsi = row.get("RSI14")
        return not pd.isna(rsi) and 30.0 <= float(rsi) <= 75.0
    if feature == "MACD":
        sma20 = row.get("SMA20")
        sma50 = row.get("SMA50")
        return not pd.isna(sma20) and not pd.isna(sma50) and float(sma20) > float(sma50)
    if feature == "EMA_CROSS":
        sma50 = row.get("SMA50")
        ps50 = prev.get("SMA50")
        sma200 = row.get("SMA200")
        p200 = prev.get("SMA200")
        return (
            not pd.isna(sma50)
            and not pd.isna(ps50)
            and not pd.isna(sma200)
            and not pd.isna(p200)
            and float(prev.get("Close", np.nan)) <= float(p200)
            and float(row.get("Close", np.nan)) > float(sma200)
        )
    if feature == "SMA_BREAKOUT":
        close = row.get("Close")
        sma50 = row.get("SMA50")
        pclose = prev.get("Close")
        ps50 = prev.get("SMA50")
        return (
            not pd.isna(close)
            and not pd.isna(sma50)
            and not pd.isna(pclose)
            and not pd.isna(ps50)
            and float(pclose) <= float(ps50)
            and float(close) > float(sma50)
        )
    if feature == "MOMENTUM":
        ret5 = row.get("Return_5d_Pct")
        return not pd.isna(ret5) and float(ret5) > 2.0
    if feature == "VOLUME_SPIKE":
        ratio = row.get("Volume_Ratio")
        return not pd.isna(ratio) and float(ratio) >= 1.5
    if feature == "ATR_BREAKOUT":
        atr = row.get("ATR_Pct")
        patr = prev.get("ATR_Pct")
        return not pd.isna(atr) and not pd.isna(patr) and float(atr) > float(patr) * 1.1
    if feature == "GAP_UP":
        gap = row.get("Gap_Pct")
        return not pd.isna(gap) and float(gap) >= 1.0
    if feature == "GAP_DOWN":
        gap = row.get("Gap_Pct")
        return not pd.isna(gap) and float(gap) <= -1.0
    if feature == "RELATIVE_STRENGTH":
        ret20 = row.get("Return_20d_Pct")
        spy20 = row.get("SPY_Return_20d_Pct")
        return (
            not pd.isna(ret20)
            and not pd.isna(spy20)
            and float(ret20) > float(spy20)
        )
    return False


def _market_filter_passes(filter_name: str, row: pd.Series) -> bool:
    if filter_name == "US_ONLY":
        return True
    if filter_name == "EU_ONLY":
        return True
    if filter_name == "UK_ONLY":
        return True
    if filter_name == "BULL_ONLY":
        return bool(row.get("SPY_Above_SMA200", False))
    if filter_name == "BEAR_ONLY":
        return not bool(row.get("SPY_Above_SMA200", True))
    if filter_name == "ABOVE_SMA200":
        return bool(row.get("Close_Above_SMA200", False))
    if filter_name == "ABOVE_SMA50":
        return bool(row.get("Close_Above_SMA50", False))
    if filter_name == "HIGH_VOLUME":
        ratio = row.get("Volume_Ratio")
        return not pd.isna(ratio) and float(ratio) >= 1.2
    if filter_name == "LOW_VOLATILITY":
        atr = row.get("ATR_Pct")
        return not pd.isna(atr) and float(atr) <= 2.5
    if filter_name == "HIGH_VOLATILITY":
        atr = row.get("ATR_Pct")
        return not pd.isna(atr) and float(atr) >= 3.0
    return True


def _simulate_trades(
    df: pd.DataFrame,
    entry_rule: str,
    exit_rule: str,
    market_filter: str,
    holding_period: int,
) -> list[tuple[float, int]]:
    if df.empty or len(df) < 220:
        return []

    entries = _parse_entry_features(entry_rule)
    trades: list[tuple[float, int]] = []
    index = df.index
    position_exit_idx: int | None = None
    entry_price = 0.0
    entry_idx = 0
    stop_price = 0.0
    peak_price = 0.0

    for i in range(1, len(df) - holding_period - 1):
        row = df.iloc[i]
        prev = df.iloc[i - 1]

        if position_exit_idx is not None and i < position_exit_idx:
            continue

        if position_exit_idx is not None and i >= position_exit_idx:
            exit_price = float(df.iloc[position_exit_idx].get("Close", np.nan))
            if entry_price > 0 and not pd.isna(exit_price):
                ret = (exit_price / entry_price) - 1.0
                hold_days = max(1, position_exit_idx - entry_idx)
                trades.append((ret, hold_days))
            position_exit_idx = None
            entry_price = 0.0

        if position_exit_idx is not None:
            continue

        if not all(_entry_feature_passes(feature, row, prev) for feature in entries):
            continue
        if not _market_filter_passes(market_filter, row):
            continue

        entry_idx = i + 1
        if entry_idx >= len(df):
            break

        entry_price = float(df.iloc[entry_idx].get("Open", df.iloc[entry_idx].get("Close", np.nan)))
        if pd.isna(entry_price) or entry_price <= 0:
            continue

        atr_pct = float(row.get("ATR_Pct", 2.0) or 2.0)
        stop_price = entry_price * (1.0 - max(0.02, (atr_pct / 100.0) * 2.0))
        peak_price = entry_price
        exit_at = min(len(df) - 1, entry_idx + holding_period)

        for j in range(entry_idx + 1, exit_at + 1):
            bar = df.iloc[j]
            close = float(bar.get("Close", np.nan))
            if pd.isna(close):
                continue

            peak_price = max(peak_price, close)

            if exit_rule == "ATR_STOP" and close <= stop_price:
                position_exit_idx = j
                break
            if exit_rule == "TRAILING_STOP" and close <= peak_price * 0.9:
                position_exit_idx = j
                break
            if exit_rule == "FIXED_STOP" and close <= entry_price * 0.95:
                position_exit_idx = j
                break
            if exit_rule == "PROFIT_TARGET" and close >= entry_price * 1.1:
                position_exit_idx = j
                break
            if exit_rule == "RSI_EXIT":
                rsi = bar.get("RSI14")
                if not pd.isna(rsi) and float(rsi) >= 70.0:
                    position_exit_idx = j
                    break
            if exit_rule == "EMA_EXIT":
                sma50 = bar.get("SMA50")
                if not pd.isna(sma50) and close < float(sma50):
                    position_exit_idx = j
                    break
            if exit_rule == "SMA_EXIT":
                sma200 = bar.get("SMA200")
                if not pd.isna(sma200) and close < float(sma200):
                    position_exit_idx = j
                    break
            if exit_rule == "TIME_EXIT" and j - entry_idx >= holding_period:
                position_exit_idx = j
                break
        else:
            position_exit_idx = exit_at

    return trades


def compute_metrics_from_trades(trades: list[tuple[float, int]]) -> dict[str, float] | None:
    if len(trades) < MIN_TRADES_FOR_METRICS:
        return None

    returns = np.array([trade[0] for trade in trades], dtype=float)
    hold_days = [trade[1] for trade in trades]

    wins = returns[returns > 0]
    losses = returns[returns <= 0]
    win_rate = float(len(wins) / len(returns)) if len(returns) else 0.0
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(abs(losses.sum())) if len(losses) else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    expectancy = float(returns.mean())
    profit_pct = float(returns.sum() * 100.0)

    equity = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(equity)
    drawdown = (equity / peak) - 1.0
    max_drawdown = float(abs(drawdown.min())) if len(drawdown) else 0.0

    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    sharpe = (expectancy / std) * math.sqrt(252.0 / max(1.0, float(np.mean(hold_days)))) if std > 0 else 0.0

    downside = returns[returns < 0]
    down_std = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    sortino = (expectancy / down_std) * math.sqrt(252.0 / max(1.0, float(np.mean(hold_days)))) if down_std > 0 else 0.0

    recovery_factor = profit_pct / (max_drawdown * 100.0) if max_drawdown > 0 else 0.0

    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(abs(losses.mean())) if len(losses) else 0.0
    if avg_win > 0:
        kelly_fraction = win_rate - ((1.0 - win_rate) * avg_loss / avg_win)
    else:
        kelly_fraction = 0.0
    kelly_fraction = max(-1.0, min(1.0, kelly_fraction))

    return {
        "profit_pct": round(profit_pct, 4),
        "max_drawdown": round(max_drawdown * 100.0, 4),
        "sharpe": round(sharpe, 4),
        "sortino": round(sortino, 4),
        "profit_factor": round(min(profit_factor, 999.0), 4),
        "win_rate": round(win_rate * 100.0, 4),
        "expectancy": round(expectancy * 100.0, 4),
        "trade_count": float(len(trades)),
        "average_hold_days": round(float(np.mean(hold_days)), 4),
        "recovery_factor": round(recovery_factor, 4),
        "kelly_fraction": round(kelly_fraction, 4),
    }


class StrategyBacktestRunner:
    """Runs one historical research job against real market data."""

    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)
        self._config = BaseResearchConfig()
        self._service = MarketDataService(self._config)
        self._price_cache: dict[tuple[str, str], pd.DataFrame] = {}
        self._spy_context: pd.DataFrame | None = None

    def run_job(
        self,
        *,
        market: str,
        time_horizon: str,
        strategy: dict[str, Any],
        data: DataAvailability,
    ) -> BacktestOutcome:
        if not data.available:
            return BacktestOutcome(status="BLOCKED", block_reason=data.block_reason or "Data unavailable")

        if not data.ohlcv_available:
            return BacktestOutcome(
                status="BLOCKED",
                block_reason="OHLCV history required for discovery strategy backtest.",
            )

        tickers = resolve_market_tickers(market, self._root)
        period = HORIZON_PERIOD.get(time_horizon, "5y")
        all_trades: list[tuple[float, int]] = []

        spy_ctx = self._get_spy_context(period)
        if spy_ctx is None or spy_ctx.empty:
            return BacktestOutcome(status="BLOCKED", block_reason="Benchmark SPY context unavailable.")

        for ticker in tickers:
            enriched = self._get_enriched(ticker, period)
            if enriched.empty:
                continue

            merged = enriched.join(
                spy_ctx[
                    [
                        c
                        for c in (
                            "SPY_Return_20d_Pct",
                            "SPY_Above_SMA200",
                        )
                        if c in spy_ctx.columns
                    ]
                ],
                how="left",
            )
            trades = _simulate_trades(
                merged,
                entry_rule=str(strategy.get("entry", "")),
                exit_rule=str(strategy.get("exit", "")),
                market_filter=str(strategy.get("market", "")),
                holding_period=int(strategy.get("holding", 10) or 10),
            )
            all_trades.extend(trades)

        metrics = compute_metrics_from_trades(all_trades)
        if metrics is None:
            return BacktestOutcome(
                status="BLOCKED",
                block_reason=(
                    f"Insufficient trades ({len(all_trades)}) for metrics; "
                    f"minimum {MIN_TRADES_FOR_METRICS} required."
                ),
                trade_count=len(all_trades),
                tickers_used=tickers,
            )

        return BacktestOutcome(
            status="COMPLETED",
            metrics=metrics,
            trade_count=int(metrics["trade_count"]),
            tickers_used=tickers,
        )

    def _get_spy_context(self, period: str) -> pd.DataFrame | None:
        cache_key = ("__SPY__", period)
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]

        raw = self._download_period("SPY", period)
        if raw.empty:
            return None
        enriched = self._service.enrich_spy(raw)
        self._price_cache[cache_key] = enriched
        return enriched

    def _get_enriched(self, ticker: str, period: str) -> pd.DataFrame:
        cache_key = (ticker, period)
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]

        raw = self._download_period(ticker, period)
        if raw.empty:
            self._price_cache[cache_key] = pd.DataFrame()
            return self._price_cache[cache_key]

        enriched = self._service.enrich_ticker(raw)
        self._price_cache[cache_key] = enriched
        return enriched

    def _download_period(self, ticker: str, period: str) -> pd.DataFrame:
        try:
            import yfinance as yf

            from momentum_continuation_research_v11 import normalize_ohlcv

            raw = yf.download(
                ticker,
                period=period,
                interval="1d",
                auto_adjust=True,
                progress=False,
            )
            return normalize_ohlcv(raw, ticker)
        except Exception as exc:
            logger.warning("Download failed for %s (%s): %s", ticker, period, exc)
            return pd.DataFrame()
