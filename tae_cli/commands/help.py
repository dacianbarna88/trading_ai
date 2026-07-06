"""TAE CLI — help command."""

from __future__ import annotations

BANNER = """=================================
TAE COMMAND CENTER

Available commands:
  health
  status
  help
================================="""


def run(_args: list[str] | None = None) -> int:
    print(BANNER)
    return 0
