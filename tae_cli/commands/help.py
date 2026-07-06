"""TAE CLI — help command."""

from __future__ import annotations

BANNER = """=================================
TAE COMMAND CENTER

Available commands:
  health
  protect
  portfolio-protect
  status
  help

  protect — run shadow profit protection + adaptive committee + context pipeline
  portfolio-protect — portfolio-level profit governor (PDG + PPG)
================================="""


def run(_args: list[str] | None = None) -> int:
    print(BANNER)
    return 0
