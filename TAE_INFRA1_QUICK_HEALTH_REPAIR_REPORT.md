# TAE INFRA-1 — Quick Health Check Repair Report

**Date:** 2026-07-06  
**Sprint:** INFRA-1  
**Mode:** INFRASTRUCTURE_ONLY · NO_BROKER · NO_LIVE_EXECUTION_CHANGE · NO_COMMIT

---

## Problem

`tae_quick_health_check.py` previously imported:

- `research_core.runtime.quick_health_report`
- `research_core.runtime.quick_health_wrapper`
- `research_core.strategy_evolution.candidate_report`

That pulled in `research_core/__init__.py` (Discovery, Hypothesis, Organisms, pandas), causing the “quick” check to hang or run slowly.

---

## Solution

Replaced the heavy import chain with a **standalone stdlib-only** script (~325 lines). No `research_core`, no `pandas`, no third-party imports.

---

## Changed files

| File | Action |
|------|--------|
| `tae_quick_health_check.py` | **Replaced** — lightweight stdlib implementation |
| `tae_quick_health_check.json` | **Generated** on run |
| `tae_quick_health_check.txt` | **Generated** on run |
| `TAE_INFRA1_QUICK_HEALTH_REPAIR_REPORT.md` | **Created** (this file) |

### Not modified (per rules)

- `live_bot.py`, `core/trades.py`, `core/portfolio.py`
- `portfolio.csv`, `live_signals.csv`
- Any broker/execution module

---

## Checks performed

| Check | Method |
|-------|--------|
| Timestamp | Local ISO timestamp in report |
| Python | `sys.executable`, `sys.version` |
| `live_bot.py` process | `pgrep -fl live_bot.py` |
| Dashboard | `pgrep` streamlit/dashboard + `lsof` ports 8501–8503 |
| Key files exist | `live_bot.py`, `dashboard_v2.py`, `portfolio.csv`, `live_signals.csv`, `watchlist.txt` |
| Log freshness | Size + mtime for 4 log files |
| Recent bot activity | Last 200 lines of `bot_output.log`; timestamp regex |
| Market evidence | Line containing `Market sessions OPEN` |
| BUY evidence | Line containing `BUY executat` |
| Advisory evidence | Line containing `TAE Live Advisory` |
| Git state | `git status --short` → CLEAN / DIRTY |
| Verdict | READY / WARNING / NOT_READY |

### Verdict logic

| Verdict | Condition |
|---------|-----------|
| **NOT_READY** | Bot not running **or** no bot log activity today |
| **WARNING** | Bot running + activity today, but autostart evidence not today **or** git DIRTY |
| **READY** | Bot running + activity today + autostart today + git CLEAN |

---

## Validation

### Run time

```bash
time python3 tae_quick_health_check.py
```

**Result:** ~0.4s wall time (no pandas/research_core import delay).

### Forbidden import AST check

```bash
python3 - <<'PY'
import ast
from pathlib import Path
tree = ast.parse(Path("tae_quick_health_check.py").read_text())
imports = []
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        imports.extend(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
        imports.append(node.module or "")
forbidden = [i for i in imports if i.startswith("research_core") or i == "pandas"]
print("FORBIDDEN_IMPORTS:", forbidden)
raise SystemExit(1 if forbidden else 0)
PY
```

**Result:** `FORBIDDEN_IMPORTS: []` — **PASS**

### py_compile

**Result:** PASS

---

## Sample run output (2026-07-06)

```
final verdict: WARNING
  live_bot: RUNNING (when pgrep available)
  activity_today: True
  git: DIRTY
  autostart today: False (startup_runner.log last run 2026-07-02)
```

Exit code: `0` for READY/WARNING, `1` for NOT_READY.

Reports written:

- `tae_quick_health_check.json`
- `tae_quick_health_check.txt`

---

## Rollback

Restore prior version from git if needed:

```bash
git checkout HEAD -- tae_quick_health_check.py
```

(Previous version re-imports `research_core` — not recommended.)

---

**No commit performed.**

*End of TAE_INFRA1_QUICK_HEALTH_REPAIR_REPORT.md*
