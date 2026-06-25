"""Universe loading for research core."""

from __future__ import annotations

from pathlib import Path

from research_core.config.base import BaseResearchConfig


def load_universe(config: BaseResearchConfig) -> list[str]:
    path = Path(config.universe_file)
    if path.exists():
        tickers = [
            line.strip().upper()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if tickers:
            return tickers
    from momentum_universe_expansion_v13 import dedupe_universe, EXPANDED_US_UNIVERSE

    return dedupe_universe(EXPANDED_US_UNIVERSE)
