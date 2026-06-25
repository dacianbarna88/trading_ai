"""Feature bin registry — add new bin definitions in V3.1+ without changing engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd


@dataclass(frozen=True)
class NumericBinSpec:
    feature: str
    label: str
    low: float
    high: float | None
    group: str


@dataclass(frozen=True)
class CategoricalBinSpec:
    column: str
    label: str
    predicate: Callable[[pd.DataFrame], pd.Series]
    group: str


def default_numeric_bins() -> list[NumericBinSpec]:
    specs: list[NumericBinSpec] = []
    for label, lo, hi, grp in [
        ("0_20", 0, 20, "RSI"), ("20_30", 20, 30, "RSI"), ("30_40", 30, 40, "RSI"),
        ("40_50", 40, 50, "RSI"), ("50_60", 50, 60, "RSI"), ("60_70", 60, 70, "RSI"),
        ("70_100", 70, None, "RSI"),
    ]:
        specs.append(NumericBinSpec("RSI14", label, lo, hi, grp))
    for label, lo, hi in [
        ("lt_m20", -999, -20), ("m20_m10", -20, -10), ("m10_0", -10, 0),
        ("0_10", 0, 10), ("10_20", 10, 20), ("gt_20", 20, None),
    ]:
        specs.append(NumericBinSpec("Dist_SMA200_Pct", label, lo, hi, "Trend"))
    for feat, grp in [("Volume_Ratio", "Volume"), ("Dollar_Volume_Ratio", "Volume")]:
        for label, lo, hi in [
            ("0_1", 0, 1), ("1_1.5", 1, 1.5), ("1.5_2", 1.5, 2),
            ("2_3", 2, 3), ("3_plus", 3, None),
        ]:
            specs.append(NumericBinSpec(feat, label, lo, hi, grp))
    for label, lo, hi, grp in [
        ("negative", -999, 0, "Price"), ("flat", 0, 1, "Price"),
        ("positive", 1, 3, "Price"), ("large_pos", 3, None, "Price"),
    ]:
        specs.append(NumericBinSpec("Gap_Pct", label, lo, hi, grp))
    for label, lo, hi in [("lt_2", 0, 2), ("2_3", 2, 3), ("3_4", 3, 4), ("4_plus", 4, None)]:
        specs.append(NumericBinSpec("ATR_Pct", label, lo, hi, "Volatility"))
    for label, lo, hi in [("lt_3", 0, 3), ("3_5", 3, 5), ("5_8", 5, 8), ("8_plus", 8, None)]:
        specs.append(NumericBinSpec("Range_Pct", label, lo, hi, "Price"))
    for label, lo, hi in [
        ("negative", -999, 0), ("0_3", 0, 3), ("3_7", 3, 7), ("7_plus", 7, None),
    ]:
        specs.append(NumericBinSpec("Intraday_Return_Pct", label, lo, hi, "Price"))
    return specs


def default_categorical_bins() -> list[CategoricalBinSpec]:
    specs: list[CategoricalBinSpec] = []
    for regime in ["BULL", "BEAR", "NEUTRAL"]:
        col = f"BIN_Regime_{regime}"
        specs.append(
            CategoricalBinSpec(
                col,
                f"Regime {regime}",
                lambda df, r=regime: df["Market_Regime"] == r,
                "Market",
            )
        )
    for col_name in [
        "Close_Above_SMA20", "Close_Above_SMA50", "Close_Above_SMA100",
        "Close_Above_SMA200", "SPY_Above_SMA200",
    ]:
        grp = "Trend" if "SMA" in col_name and "SPY" not in col_name else "Market"
        specs.append(
            CategoricalBinSpec(
                f"BIN_{col_name}_above",
                f"{col_name} above",
                lambda df, c=col_name: df[c] == True,
                grp,
            )
        )
        specs.append(
            CategoricalBinSpec(
                f"BIN_{col_name}_below",
                f"{col_name} below",
                lambda df, c=col_name: df[c] == False,
                grp,
            )
        )
    return specs


class FeatureBinRegistry:
    """Registry of bin specs — register additional specs in future versions."""

    def __init__(self) -> None:
        self._numeric: list[NumericBinSpec] = []
        self._categorical: list[CategoricalBinSpec] = []

    def register_defaults(self) -> None:
        self._numeric.extend(default_numeric_bins())
        self._categorical.extend(default_categorical_bins())

    def register_numeric(self, spec: NumericBinSpec) -> None:
        self._numeric.append(spec)

    def register_categorical(self, spec: CategoricalBinSpec) -> None:
        self._categorical.append(spec)

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        for spec in self._numeric:
            col_name = f"BIN_{spec.feature}_{spec.label}"
            if spec.high is None:
                out[col_name] = out[spec.feature] >= spec.low
            else:
                out[col_name] = (out[spec.feature] >= spec.low) & (out[spec.feature] < spec.high)
        for sector in out["Sector"].unique():
            safe = str(sector).replace(" ", "_")
            out[f"BIN_Sector_{safe}"] = out["Sector"] == sector
        for spec in self._categorical:
            out[spec.column] = spec.predicate(out)
        return out

    def bin_column_groups(self, df: pd.DataFrame) -> dict[str, str]:
        groups: dict[str, str] = {}
        for spec in self._numeric:
            groups[f"BIN_{spec.feature}_{spec.label}"] = spec.group
        for spec in self._categorical:
            groups[spec.column] = spec.group
        for sector in df["Sector"].unique():
            groups[f"BIN_Sector_{str(sector).replace(' ', '_')}"] = "Sector"
        return groups

