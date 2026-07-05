# TAE X.INFRA-HEALTH-1 — Permission-safe Crontab Handling

**Date:** 2026-07-05  
**Mode:** SHADOW_ONLY | PAPER_ONLY | NO_BROKER  
**Commit:** None (per sprint instructions)

## Goal

Prevent `tae_infrastructure_health.py` from crashing when `crontab -l` cannot be spawned in sandbox or other restricted contexts.

## Root cause (prior audit)

`get_crontab()` called `subprocess.run(["crontab", "-l"])` without handling spawn failures. macOS raised uncaught `PermissionError`, aborting the report and causing intelligence runner Step 1 to FAIL with exit code 1 and an empty stdout tail.

## Minimal patch

### `get_crontab()` — return structured availability

```python
def get_crontab() -> tuple[str, bool]:
    """Return (crontab_text, available). available=False when spawn is blocked."""
    try:
        result = _run(["crontab", "-l"])
    except (PermissionError, OSError):
        return "", False
    if result.returncode != 0:
        return "", True
    return result.stdout or "", True
```

### `build_health_report()` — WARN instead of crash

- When `crontab_available` is `False`:
  - Skip individual `cron:{pattern}` and `cron_duplicate:{pattern}` checks (avoids false FAIL for missing entries).
  - Emit **`cron:access` → WARN** with detail `"crontab unavailable in this context (sandbox or restricted permissions)"`.
- When crontab is accessible: unchanged PASS/FAIL behavior for cron pattern checks.
- Injected `crontab_fn` in tests still treated as available (preserves existing test behavior).

### Tests added

| Test | Purpose |
|------|---------|
| `test_get_crontab_spawn_blocked_returns_unavailable` | `_run` raises `PermissionError` → `("", False)` |
| `test_crontab_unavailable_warn_completes_report` | Full report completes; `cron:access` WARN; no cron FAIL checks |

## Files changed

| File | Change |
|------|--------|
| `tae_infrastructure_health.py` | Permission-safe `get_crontab()` + WARN path in report builder |
| `tae_infrastructure_health_test.py` | 2 new tests |

**Unchanged:** `live_bot.py`, `portfolio.csv`, `live_signals.csv`, BUY/SELL execution paths.

## Validation

| Check | Result |
|-------|--------|
| `python3 -m py_compile tae_infrastructure_health.py` | PASS |
| `python3 -m unittest tae_infrastructure_health_test.py` | **21/21 PASS** |
| Standalone (sandbox) | **No crash**; report written; `cron:access` **WARN** |
| Standalone (full permissions) | **Overall PASS**, exit 0 — prior behavior preserved |
| Intelligence runner Step 1 (sandbox) | **No PermissionError**; completes (exit 1 only if other checks FAIL, e.g. launchctl in sandbox) |
| Intelligence runner Step 1 (full permissions) | **PASS**, exit 0, ~0.45s |
| Live execution files | **Unchanged** |

### Before vs after (sandbox)

| Metric | Before | After |
|--------|--------|-------|
| Exception | `PermissionError: crontab` | None |
| Report JSON written | No | Yes |
| `cron:access` check | N/A (crash) | WARN |
| Step 1 stderr | Traceback tail | Empty |

### Full-permission regression

```
Overall: PASS
Autostart readiness: READY
PASS/INFO/WARN/FAIL: 38 4 0 0
EXIT=0
```

Cron pattern checks still PASS when crontab is readable.

## Notes

- Sandbox may still report overall **FAIL** or Step 1 **FAIL** if other subprocess checks fail (e.g. `launchctl list` returning no loaded agents). That is separate from this fix; the crontab crash path is resolved.
- Future work (out of scope): apply the same spawn-safe pattern to `launchctl` / `pgrep` if sandbox-complete PASS is desired.

## Commit status

**Stopped without commit.**
