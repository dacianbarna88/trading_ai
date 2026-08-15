"""TAE CLI — conversion-breakthrough command (opportunity→order audit)."""

from __future__ import annotations


def run(_args: list[str] | None = None) -> int:
    import sys
    if _args and _args[0] == "attrition":
        sys.argv = ["tae_conversion_breakthrough", "attrition"]
    from tae_conversion_breakthrough import main

    return main()
