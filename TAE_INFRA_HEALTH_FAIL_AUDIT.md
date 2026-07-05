# TAE X.INFRA-HEALTH-AUDIT — Step 1 Failure Investigation

**Date:** 2026-07-05  
**Scope:** READ ONLY — no code changes, no fixes applied  
**Mode:** SHADOW_ONLY | PAPER_ONLY | NO_BROKER

## Executive summary

Step 1 `infrastructure_health` fails in `tae_market_open_intelligence_runner.py` **not because infrastructure is unhealthy**, but because `tae_infrastructure_health.py` **crashes with an uncaught exception** when it cannot spawn the `crontab` subprocess.

| Question | Answer |
|----------|--------|
| Real infrastructure issue? | **No** — full-permission run: **PASS / READY** (38 PASS, 0 FAIL) |
| Stale test expectation? | **No** — unit tests mock `crontab_fn`; they never hit live `crontab` |
| Missing file? | **No** — crash occurs before file checks complete |
| Path/env issue? | **Yes** — sandbox / restricted subprocess context blocks `crontab` |
| Harmless warning marked FAIL? | **Partially** — worse than that: **unhandled crash (exit 1)**, not a structured FAIL check |

**Verdict:** False-positive pipeline FAIL caused by **environment restriction + missing exception handling** in `get_crontab()`. Production LaunchAgent runs (2026-07-03) previously passed Step 1.

---

## Module under inspection

| Item | Value |
|------|-------|
| Script | `tae_infrastructure_health.py` |
| Role | Autostart / permissions audit (LaunchAgents, crontab, scripts, logs) |
| Exit semantics | `main()` returns `1` if `overall_status == "FAIL"` **or** if an uncaught exception occurs |
| First external call in `build_health_report()` | `get_crontab()` → `subprocess.run(["crontab", "-l"])` at line 329 |

---

## Failure evidence (intelligence runner)

From `tae_market_open_intelligence_runner.json` (run **2026-07-05T20:31:02**):

```json
{
  "id": "infrastructure_health",
  "script": "tae_infrastructure_health.py",
  "status": "FAIL",
  "exit_code": 1,
  "duration_seconds": 0.19,
  "detail": "Exit code 1",
  "stderr_tail": "... PermissionError: [Errno 1] Operation not permitted: 'crontab'"
}
```

From `market_open_intelligence_runner.log`:

| Run timestamp | Step 1 result | Notes |
|---------------|---------------|-------|
| 2026-07-03T16:26:46 | **PASS** (0.39s) | Full user/LaunchAgent context |
| 2026-07-05T20:31:02 | **FAIL** (0.19s) | Cursor sandbox / restricted subprocess |

The ~0.19s duration and empty stdout indicate the script **terminated early via traceback**, not after completing checks.

---

## Standalone reproduction

### A. Restricted environment (matches intelligence runner FAIL)

```text
$ python3 tae_infrastructure_health.py

Traceback (most recent call last):
  ...
  File "tae_infrastructure_health.py", line 329, in build_health_report
    crontab_text = crontab_fn() if crontab_fn else get_crontab()
  File "tae_infrastructure_health.py", line 107, in get_crontab
    result = _run(["crontab", "-l"])
  File "tae_infrastructure_health.py", line 59, in _run
    return subprocess.run(...)
PermissionError: [Errno 1] Operation not permitted: 'crontab'

EXIT_CODE=1
```

No `tae_infrastructure_health.json` refresh on crash path (stale JSON from prior successful run may remain).

### B. Full user permissions (production-like)

```text
$ python3 tae_infrastructure_health.py

===== TAE INFRASTRUCTURE HEALTH =====
Overall: PASS
Autostart readiness: READY
PASS/INFO/WARN/FAIL: 38 4 0 0
Wrote: tae_infrastructure_health.json tae_infrastructure_health.md
EXIT_CODE=0
```

All infrastructure checks pass: scripts present/executable, crontab entries found, LaunchAgents loaded, bot/dashboard running, logs OK.

---

## Root cause analysis

### Crash location

```python
def get_crontab() -> str:
    result = _run(["crontab", "-l"])
    if result.returncode != 0:
        return ""
    return result.stdout or ""
```

`_run()` uses `subprocess.run(..., check=False)` but does **not** catch spawn failures. On macOS in restricted contexts, spawning `crontab` raises:

```text
PermissionError: [Errno 1] Operation not permitted: 'crontab'
```

This propagates uncaught through `build_health_report()` → `main()` → exit code **1**.

### Why intelligence runner marks FAIL

`tae_market_open_intelligence_runner.run_module()` treats any non-zero exit as:

```python
status = "PASS" if result.returncode == 0 else "FAIL"
```

It cannot distinguish:

1. **Legitimate audit FAIL** (`overall_status == "FAIL"` after full report), vs  
2. **Script crash** (uncaught exception before report generation)

Both return exit code 1.

### Why Jul 3 passed but Jul 5 failed

| Context | `crontab` spawn | Step 1 outcome |
|---------|-----------------|----------------|
| LaunchAgent / normal terminal (Jul 3) | Allowed | PASS |
| Cursor agent sandbox (Jul 5 validation) | Blocked (`Operation not permitted`) | FAIL (crash) |

This is an **execution-context** difference, not an infrastructure regression.

### Other subprocess calls (not reached on crash path)

If `crontab` were handled gracefully, later calls could also fail in sandbox:

- `launchctl list`
- `pgrep -f`
- `xattr -l`
- `plutil -lint`

Tests avoid this by injecting `crontab_fn`, `launchctl_fn`, and `pgrep_fn` mocks (`tae_infrastructure_health_test.py`).

---

## Infrastructure state (when script completes)

Latest successful audit (**2026-07-05T20:33:43**, full permissions):

| Area | Status |
|------|--------|
| Runner scripts (4) | PASS — present, executable, bash -n OK |
| Crontab entries | PASS — market_close, session_guard, daily_intelligence |
| LaunchAgents (3) | PASS — loaded |
| awake_guard / caffeinate | PASS |
| live_bot.py | PASS — 1 process |
| dashboard | PASS — 1 process |
| venv python | PASS |
| LaunchAgent logs | PASS |
| **Overall** | **PASS / READY** |

Observation (non-blocking): `com.tradingai.market-open` reports `last_exit=78` but is classified PASS (only 126/127 trigger FAIL). Not related to current Step 1 crash.

---

## Classification matrix

| Category | Applies? | Evidence |
|----------|----------|----------|
| Real infrastructure issue | ❌ | Full-permission audit: 38 PASS, 0 FAIL |
| Stale test expectation | ❌ | Tests use injected fns; expectations align with mocked PASS/FAIL |
| Missing file | ❌ | Scripts, plists, venv all present when audit completes |
| Path/env issue | ✅ | Sandbox blocks `crontab` subprocess spawn |
| Harmless warning → FAIL | ⚠️ Partial | Not a WARN check — **uncaught exception** masquerading as FAIL |

---

## Impact on market-open pipeline

- Steps 2–11 continue after Step 1 FAIL (runner design: log and proceed).
- Shadow intelligence and governor outputs still refresh.
- Overall runner status becomes **FAIL** solely due to Step 1 crash in restricted contexts.
- **No impact on live_bot.py, BUY/SELL, or broker paths.**

---

## Recommended fix direction (NOT implemented)

For a future sprint (not this audit):

1. Wrap `_run()` or `get_crontab()` to catch `PermissionError` / `OSError` on spawn.
2. Emit a structured check e.g. `cron:access` → **WARN** with detail `"crontab unavailable in this context"`.
3. Optionally apply same pattern to `launchctl`, `pgrep`, `xattr`.
4. Consider distinct exit codes: crash vs audit FAIL (or always write partial JSON before exit).

---

## Validation performed

| Check | Result |
|-------|--------|
| Inspected `tae_infrastructure_health.py` | Done |
| Standalone run (restricted) | Reproduced PermissionError crash |
| Standalone run (full permissions) | PASS / exit 0 |
| Reviewed intelligence runner stderr capture | Matches crash traceback |
| Reviewed historical log | Jul 3 PASS vs Jul 5 FAIL |
| Code changes | **None** |
| Commit | **Stopped without commit** |
