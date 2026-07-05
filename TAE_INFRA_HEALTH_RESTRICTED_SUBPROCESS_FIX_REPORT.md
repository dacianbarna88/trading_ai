# TAE X.INFRA-HEALTH-2 — Permission-safe Restricted Subprocess Handling

**Date:** 2026-07-05  
**Mode:** SHADOW_ONLY | PAPER_ONLY | NO_BROKER  
**Commit:** None (per sprint instructions)

## Goal

Generalize spawn-safe handling for macOS subprocesses used by `tae_infrastructure_health.py`, especially `launchctl`, so restricted environments produce **WARN** and complete reports instead of uncaught exceptions or false **FAIL** checks.

## Subprocess inventory

| Call site | Command | Restricted behavior (after fix) |
|-----------|---------|----------------------------------|
| `get_crontab()` | `crontab -l` | `cron:access` WARN; skip cron pattern FAILs |
| `launchctl_labels()` | `launchctl list` | `launchctl:access` WARN; skip launchagent FAILs |
| `pgrep_count()` | `pgrep -f` | `pgrep:access` WARN; process checks unverified WARN |
| `bash_syntax_ok()` | `bash -n` | `bash:access` WARN (if blocked) |
| `validate_plist_checks()` | `plutil -lint` | per-plist WARN (if blocked) |
| `read_xattrs()` | `xattr -l` | empty attrs via safe `_run()` (no crash) |

## Minimal patch

### Central `_run()` wrapper

All subprocess spawns route through `_run()`, which catches `PermissionError` / `OSError` and returns `CompletedProcess` with `returncode = SPAWN_BLOCKED (-999)`.

```python
def _run(cmd, *, cwd=None):
    try:
        return subprocess.run(...)
    except (PermissionError, OSError) as exc:
        return subprocess.CompletedProcess(cmd, SPAWN_BLOCKED, "", str(exc))
```

### Availability tuples

| Function | Returns |
|----------|---------|
| `get_crontab()` | `(text, available)` |
| `launchctl_labels()` | `(labels, available)` — also `available=False` when `launchctl list` exits non-zero (sandbox rc=1) |
| `pgrep_count()` | `(count, available)` — rc=1 (no matches) remains available |

### Report builder WARN gates

When subprocess family unavailable:

- **`cron:access`** — skip `cron:{pattern}` FAIL checks
- **`launchctl:access`** — skip `launchagent:{label}` FAIL checks
- **`pgrep:access`** — mark caffeinate / live_bot / dashboard as unverified WARN

`main()` exit code remains **0** for overall **WARN** (intelligence runner Step 1 PASS).

## Files changed

| File | Change |
|------|--------|
| `tae_infrastructure_health.py` | Safe `_run()`, availability tuples, WARN gates |
| `tae_infrastructure_health_test.py` | 3 new/updated tests (crontab, launchctl spawn, launchctl rc≠0, launchctl report) |

**Unchanged:** `live_bot.py`, execution paths, BUY/SELL, broker.

## Validation

| Check | Result |
|-------|--------|
| `python3 -m py_compile tae_infrastructure_health.py` | PASS |
| `python3 -m unittest tae_infrastructure_health_test.py` | **24/24 PASS** |
| Standalone (sandbox) | **WARN**, exit **0**, 0 FAIL; warns: `cron:access`, `launchctl:access`, process unverified |
| Standalone (full permissions) | **PASS**, exit **0** — 38 PASS / 0 FAIL (preserved) |
| Intelligence Step 1 (sandbox) | **PASS**, exit **0** |
| Intelligence Step 1 (full permissions) | **PASS**, exit **0** |
| `live_bot.py` | **Unchanged** |

### Before vs after (sandbox)

| Metric | X.INFRA-HEALTH-1 | X.INFRA-HEALTH-2 |
|--------|------------------|------------------|
| Crash on crontab | Fixed | Fixed |
| Overall status | FAIL | **WARN** |
| Exit code | 1 | **0** |
| launchagent FAILs | 3 | **0** |
| Step 1 intelligence runner | FAIL | **PASS** |

## Notes

- `pgrep` return code **1** (no matching processes) is still treated as **available** — only spawn-blocked pgrep triggers `pgrep:access` WARN.
- `launchctl list` non-zero exit (observed rc=1 in sandbox) is treated as unavailable to avoid false “not loaded” FAILs when the tool cannot enumerate agents.
- Full-permission production path unchanged: launchctl rc=0, crontab readable, pgrep operational → **PASS / READY**.

## Commit status

**Stopped without commit.**
