"""Base configuration shared by every research module."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from research_core.constants import (
    DEFAULT_ENTRY_MODE,
    DEFAULT_FILTER_MODE,
    DEFAULT_HISTORY_PERIOD,
    DEFAULT_THRESHOLD_PCT,
)
from research_core.config.sectors import SECTOR_GROUPS


@dataclass
class BaseResearchConfig:
    """
    Common settings for all research modules.
    Module-specific configs extend this — never duplicate universe/history/safety fields.
    """

    module_id: str = "base"
    version: str = "0.0"
    output_dir: str = "."

    universe_file: str = "us_expanded_universe.txt"
    history_period: str = DEFAULT_HISTORY_PERIOD
    threshold_pct: float = DEFAULT_THRESHOLD_PCT
    filter_mode: str = DEFAULT_FILTER_MODE
    hold_days: int = 60
    entry_mode: str = DEFAULT_ENTRY_MODE
    atr_period: int = 14
    return_column: str = "Return_60d"

    extra: dict = field(default_factory=dict)

    def sector_map(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for sector, tickers in SECTOR_GROUPS.items():
            for ticker in tickers:
                mapping[ticker.upper()] = sector
        return mapping

    def resolve_output_dir(self, override: str | Path | None = None) -> Path:
        if override is not None:
            return Path(override)
        return Path(self.output_dir)
