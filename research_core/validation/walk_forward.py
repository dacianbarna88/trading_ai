"""Walk-forward validation (V2.1 methodology)."""

from __future__ import annotations

import pandas as pd

from research_core.config.discovery import DiscoveryConfig
from research_core.metrics.performance import compute_metrics


def years_offset(base: pd.Timestamp, years: float) -> pd.Timestamp:
    return base + pd.Timedelta(days=int(years * 365.25))


def months_offset(base: pd.Timestamp, months: float) -> pd.Timestamp:
    return base + pd.Timedelta(days=int(months * 30.4375))


class WalkForwardValidator:
    """Expanded rolling walk-forward from V2.1 — pluggable in V3.1+."""

    def __init__(self, config: DiscoveryConfig) -> None:
        self._config = config

    def build_test_windows(
        self,
        min_date: pd.Timestamp,
        max_date: pd.Timestamp,
    ) -> list[dict]:
        windows: list[dict] = []
        step_delta = months_offset(min_date, self._config.roll_step_months) - min_date
        for cfg_name, train_y, test_y in self._config.rolling_configs:
            cursor = min_date
            fold = 0
            while True:
                train_end = years_offset(cursor, train_y)
                test_start = train_end
                test_end = years_offset(train_end, test_y)
                if train_end >= max_date:
                    break
                actual_end = min(test_end, max_date)
                if test_start >= actual_end:
                    cursor = cursor + step_delta
                    continue
                fold += 1
                windows.append(
                    {
                        "config": cfg_name,
                        "fold": fold,
                        "test_start": test_start,
                        "test_end": actual_end,
                    }
                )
                cursor = cursor + step_delta
                if cursor >= max_date:
                    break
        return windows

    def score(
        self,
        df: pd.DataFrame,
        mask: pd.Series,
        windows: list[dict],
        return_col: str,
    ) -> tuple[float, int, int]:
        cfg = self._config
        passes = 0
        valid = 0
        for w in windows:
            wmask = (
                (df["Signal_Date"] > w["test_start"])
                & (df["Signal_Date"] <= w["test_end"])
            )
            base_rets = df.loc[wmask, return_col].astype(float).values
            cand_rets = df.loc[wmask & mask, return_col].astype(float).values
            if len(cand_rets) < cfg.min_wf_valid_trades:
                continue
            valid += 1
            base_m = compute_metrics(
                base_rets,
                {
                    "Avg_Return": float(base_rets.mean()),
                    "Win_Rate": float((base_rets > 0).mean() * 100),
                },
            )
            cand_m = compute_metrics(cand_rets, base_m)
            if self._split_passes(cand_m, base_m):
                passes += 1
        wf_score = (passes / valid * 100.0) if valid else 0.0
        return round(wf_score, 2), passes, valid

    def _split_passes(self, cand_m: dict, base_m: dict) -> bool:
        cfg = self._config
        return (
            cand_m["Avg_Return"] > base_m["Avg_Return"]
            and cand_m["Win_Rate"] > base_m["Win_Rate"]
            and cand_m["Profit_Factor"] > base_m["Profit_Factor"]
            and cand_m["Avg_Return"] > 0
            and cand_m["Win_Rate"] > cfg.min_wf_win_pct
        )
