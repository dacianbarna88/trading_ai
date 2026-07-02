# TAE INFRA-3 — Startup / LaunchAgent / Autostart Reliability Fix Report

**Date:** 2026-07-02  
**Sprint:** INFRA-3  
**Scope:** Infrastructure only — trading logic untouched

---

## 1. Root cause of `com.tradingai.startup` exit 126

Three compounding issues:

| Issue | Evidence | Impact |
|-------|----------|--------|
| **macOS TCC blocks launchd → bash → Desktop `.sh`** | `startup_launchagent.err.log`: `Operation not permitted` on `startup_runner.sh` | Exit **126** (permission denied) |
| **`getcwd` failure on Desktop WorkingDirectory** | `shell-init: error retrieving current directory: getcwd: cannot access parent directories: Operation not permitted` | Bash fails before script body runs |
| **`GUARD_ARGS[@]: unbound variable`** | `startup_runner.log` (with `set -u`) | Script crash when no dry-run args passed |

Same TCC class as INFRA-1 cron failure. LaunchAgents in the **user GUI domain** can run **venv Python on Desktop** (proven by `com.tradingai.market-session-guard`), but **direct `/bin/bash script.sh` on Desktop** is blocked under launchd at login.

**Fix applied:** Python launcher (`tae_startup_launcher.py`) invoked via `venv/bin/python3` in the startup plist — same pattern that resolved exit 126 for market-session-guard in prior infra work.

---

## 2. Files changed

| File | Change |
|------|--------|
| `launchagents/com.tradingai.startup.plist` | Rewritten: `venv/bin/python3` + `tae_startup_launcher.py`, separate out/err logs, `TAE_SCHEDULER_SOURCE=launchagent` |
| `launchagents/com.tradingai.market-session-guard.plist` | Uniformized in repo (matches installed) |
| `tae_startup_launcher.py` | **New** — LaunchAgent-safe startup (awake guard, pgrep anti-duplicate, market_session_guard) |
| `startup_runner.sh` | Fixed `GUARD_ARGS` unbound bug; anti-duplicate guards; clear `STARTUP:` logs; kept for manual / `@reboot` cron |
| `tae_infrastructure_health.py` | Full INFRA-3 checks: 3 LaunchAgents, plists, exit 126, logs, cron duplicates, process counts |
| `tae_infrastructure_health_test.py` | 16 tests covering exit 126, provenance WARN, duplicates, plists, cron |
| `~/Library/LaunchAgents/com.tradingai.*.plist` | Installed from repo |

**Not modified:** `live_bot.py`, BUY/SELL/Risk/Broker, Market Data Layer, intraday/knowledge modules.

---

## 3. Plist status

| Plist | plutil | Program | WorkingDirectory | Logs |
|-------|--------|---------|------------------|------|
| `com.tradingai.startup` | OK | `venv/bin/python3` → `tae_startup_launcher.py` | `/Users/book/Desktop/trading_ai` | `startup_launchagent.out.log` / `.err.log` |
| `com.tradingai.market-open` | OK | `/bin/bash` → `market_open_runner.sh` | set | `market_open_launchagent.out.log` / `.err.log` |
| `com.tradingai.market-session-guard` | OK | `venv/bin/python3` → `market_session_guard.py` | set | `market_session_guard_launchd.log` |

All three plist sources live in `launchagents/` and are installed under `~/Library/LaunchAgents/`.

---

## 4. launchctl status (post-fix)

```
-  0  com.tradingai.market-open
-  0  com.tradingai.startup
-  0  com.tradingai.market-session-guard
```

Startup **exit 126 → exit 0** after python launcher migration and plist reload.

Startup launcher run (with bot/dashboard already up):

```
STARTUP: live_bot already running
STARTUP: dashboard already running
STARTUP: skipping market_session_guard (bot and dashboard already up)
```

Active bot was **not** stopped or restarted.

---

## 5. Health checker result

```
Overall: WARN
Autostart readiness: DEGRADED
PASS/WARN/FAIL: 34 / 8 / 0
```

Outputs: `tae_infrastructure_health.json`, `tae_infrastructure_health.md`

Expected WARN items:

- `com.apple.provenance` on infra scripts (WARN only, not FAIL)
- `@reboot` cron still calls `startup_runner.sh` (duplicate with LaunchAgent startup — WARN)
- Historical bash TCC lines remain in `startup_launchagent.err.log` (WARN; python launcher now active)

No FAIL checks after fix.

---

## 6. Tests result

```
python3 -m py_compile tae_infrastructure_health.py tae_startup_launcher.py  → OK
python3 tae_infrastructure_health_test.py                                   → 16/16 OK
bash -n startup_runner.sh market_open_runner.sh market_close_runner.sh awake_guard.sh → OK
plutil -lint ~/Library/LaunchAgents/com.tradingai*.plist                    → OK
```

---

## 7. Cron status

| Entry | Status |
|-------|--------|
| `market_open_runner.sh` | **Removed** (LaunchAgent primary) |
| `market_session_guard.py` | Present (`*/5` Mon–Fri) |
| `daily_intelligence_runner.py` | Present (`*/30`) |
| `market_close_runner.sh` | Present (`15 23` Mon–Fri) |
| `@reboot startup_runner.sh` | Present — **WARN** duplicate with LaunchAgent; may still hit TCC on cold reboot via cron |

---

## 8. Remaining risks

1. **`@reboot` cron + bash** — Reboot path still uses `startup_runner.sh` via cron/bash; may fail TCC while LaunchAgent succeeds at login. Consider removing `@reboot` cron after one successful reboot validation.
2. **`com.tradingai.market-open`** — Still uses `/bin/bash` + `.sh`; first real scheduled run is **Monday 09:50**. If TCC blocks, migrate to python wrapper (same pattern as startup).
3. **Desktop folder TCC** — Long-term, moving the project out of `~/Desktop/` reduces macOS privacy friction.
4. **Historical err log** — Old bash errors in `startup_launchagent.err.log`; safe to truncate after next login cycle confirms python launcher only.

---

## 9. Monday market-open validation

First production test of `com.tradingai.market-open`:

- **When:** Monday after **09:50** local
- **Check:** `market_open_launchagent.out.log`, `market_open_launchagent.err.log`
- **Expect:** No `Operation not permitted`; bot/dashboard start only if not already running (pgrep guards)

---

## 10. Trading logic confirmation

| Item | Status |
|------|--------|
| `live_bot.py` | **Untouched** |
| BUY / SELL / Risk / Broker / Trailing | **Untouched** |
| Market Data Layer | **Untouched** |
| Intraday / knowledge modules | **Untouched** |
| Mode | **ANALYSIS_ONLY \| PAPER_ONLY \| NO_BROKER \| NO_EXECUTION** unchanged |

---

## 11. Git

No commit made (per instructions).
