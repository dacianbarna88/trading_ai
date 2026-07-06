"""TAE CLI-1 — command dispatcher."""

from __future__ import annotations

import sys

from tae_cli.commands import health, help as help_cmd, policy, portfolio_protect, protect, status

COMMANDS = {
    "health": health.run,
    "protect": protect.run,
    "portfolio-protect": portfolio_protect.run,
    "policy": policy.run,
    "status": status.run,
    "help": help_cmd.run,
}


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    command = args[0].lower() if args else "help"
    handler = COMMANDS.get(command)
    if handler is None:
        print(f"Unknown command: {command}", file=sys.stderr)
        help_cmd.run([])
        return 2
    return int(handler(args[1:]))
