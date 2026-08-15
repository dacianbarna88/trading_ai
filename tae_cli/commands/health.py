"""TAE CLI — health command (delegates to tae_quick_health_check).

Quick Health persistence and live-advisory refresh share one orchestration path
in ``tae_quick_health_check.main()`` (post-health ``LiveAdvisoryBridge`` hook).
"""

from __future__ import annotations


def run(_args: list[str] | None = None) -> int:
    """Delegate to HEAD quick-health SSOT (main takes no CLI args)."""
    import tae_quick_health_check as qhc

    # Provenance: x12b health wrapper passed args; HEAD tae_quick_health_check.main()
    # is zero-arg (REUSE_HEAD_COMPONENT). Keep wrapper; adapt call site only.
    _ = _args
    return int(qhc.main())
