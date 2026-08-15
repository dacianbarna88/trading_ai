"""TAE CLI — exit-replay-horizon-audit (READ_ONLY wrapper)."""

from __future__ import annotations


def run(args: list[str] | None = None) -> int:
    import tae_exit_replay_horizon_audit as audit

    return int(audit.main(args))
