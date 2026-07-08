"""TAE CLI — canonical-vs-paper comparison command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
REPORT_MD = ROOT / "TAE_CANONICAL_VS_PAPER_REPORT.md"


def run(_args: list[str] | None = None) -> int:
    print("===== TAE CANONICAL-VS-PAPER — READ ONLY =====")
    print("Mode: PAPER_ONLY | compares accounting snapshot vs paper portfolio")
    print("")
    code = int(
        subprocess.run(
            [
                sys.executable,
                "-c",
                "from tae_paper_execution import compare_canonical_vs_paper; import sys; "
                "r=compare_canonical_vs_paper(); sys.exit(0 if r.get('ok') else 1)",
            ],
            cwd=ROOT,
            check=False,
        ).returncode
    )
    if code != 0:
        return code
    if REPORT_MD.is_file():
        print(REPORT_MD.read_text(encoding="utf-8"))
    return 0
