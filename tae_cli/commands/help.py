"""TAE CLI — help command."""

from __future__ import annotations

BANNER = """=================================
TAE COMMAND CENTER

Available commands:
  health
  protect
  portfolio-protect
  policy
  growth-analytics
  opportunity
  winner
  status
  help

  protect — run shadow profit protection + adaptive committee + context pipeline
  portfolio-protect — portfolio-level profit governor (PDG + PPG)
  policy — adaptive profit policy memory + evaluation (PPG + APPE)
  growth-analytics — profit growth analytics SSOT (read-only join)
  opportunity — opportunity cost ledger (why profit was missed)
  winner — winner lifecycle profiler (how winners grow and die)
================================="""


def run(_args: list[str] | None = None) -> int:
    print(BANNER)
    return 0
