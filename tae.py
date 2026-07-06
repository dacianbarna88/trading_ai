#!/usr/bin/env python3
"""
TAE CLI-1 — Official Command Center

INFRASTRUCTURE_ONLY | NO_BROKER | NO_LIVE_EXECUTION_CHANGE

Single entry point that orchestrates existing TAE scripts.
Does not replace or remove standalone scripts.
"""

from __future__ import annotations

import sys

from tae_cli.dispatcher import main

if __name__ == "__main__":
    sys.exit(main())
