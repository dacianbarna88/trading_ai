"""TAE CLI — learning-economic-ablation (PAPER ONLY)."""

from __future__ import annotations

import sys


def run(args: list[str] | None = None) -> int:
    argv = list(args or [])
    print("===== TAE LEARNING-ECONOMIC-ABLATION — PAPER ONLY =====")
    print("Mode: PAPER_ONLY | NO_BROKER | NO_SSOT_MUTATION | DETERMINISTIC")
    print("")
    from tae_learning_economic_ablation import main

    return int(main(argv))
