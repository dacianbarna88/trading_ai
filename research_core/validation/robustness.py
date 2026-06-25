"""Robustness and diversification checks."""

from __future__ import annotations

import pandas as pd

from research_core.config.discovery import DiscoveryConfig


class RobustnessValidator:
    """Ticker/sector/time stability checks — extend with new tests in V3.1+."""

    def __init__(self, config: DiscoveryConfig) -> None:
        self._config = config

    def evaluate(
        self,
        df: pd.DataFrame,
        mask: pd.Series,
        baseline: dict,
        return_col: str,
    ) -> tuple[float, list[str]]:
        cfg = self._config
        sub = df[mask]
        issues: list[str] = []
        if sub.empty:
            return 0.0, ["no_trades"]

        ticker_counts = sub["Ticker"].value_counts()
        top_ticker_share = ticker_counts.iloc[0] / len(sub)
        if top_ticker_share > cfg.max_top_ticker_share:
            issues.append(f"ticker_concentration_{round(top_ticker_share * 100, 1)}%")

        sector_counts = sub["Sector"].value_counts()
        top_sector_share = sector_counts.iloc[0] / len(sub)
        sectors_with_min = int(
            (sub.groupby("Sector").size() >= cfg.min_sector_trades).sum()
        )
        if top_sector_share > cfg.max_top_sector_share:
            issues.append(f"sector_concentration_{round(top_sector_share * 100, 1)}%")
        if sectors_with_min < cfg.min_sectors_with_edge:
            issues.append("sector_diversity_low")

        sorted_tickers = sorted(df["Ticker"].unique())
        mid = len(sorted_tickers) // 2
        split_pass = 0
        for half in [set(sorted_tickers[:mid]), set(sorted_tickers[mid:])]:
            hsub = sub[sub["Ticker"].isin(half)]
            if len(hsub) < 20:
                continue
            if float(hsub[return_col].mean()) > baseline["Avg_Return"]:
                split_pass += 1
        if split_pass < 2:
            issues.append("ticker_split_failure")

        max_date = df["Signal_Date"].max()
        time_pos = 0
        for years in [10, 5, 3, 2, 1]:
            cutoff = max_date - pd.Timedelta(days=int(years * 365.25))
            wsub = sub[sub["Signal_Date"] >= cutoff]
            if len(wsub) >= 15 and float(wsub[return_col].mean()) > 0:
                time_pos += 1
        if time_pos < 3:
            issues.append(f"time_window_stability_{time_pos}_of_5")

        score = (
            min(top_ticker_share / cfg.max_top_ticker_share, 1.0) * 25
            + min(sectors_with_min / 5.0, 1.0) * 25
            + split_pass / 2.0 * 25
            + time_pos / 5.0 * 25
        )
        return round(score, 2), issues
