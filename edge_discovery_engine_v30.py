"""
Edge Discovery Engine V3.0 — entry point for the Scientific Research Core.

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Implementation lives in `research_core/` for long-term maintainability.
This file is the versioned runner only.
"""

from __future__ import annotations

from research_core.config import ResearchConfig
from research_core.discovery.engine import DiscoveryEngine


def main() -> None:
    engine = DiscoveryEngine(ResearchConfig.v30_default())
    engine.run()


if __name__ == "__main__":
    main()
