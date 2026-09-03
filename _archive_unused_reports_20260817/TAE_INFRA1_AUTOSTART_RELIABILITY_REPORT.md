# TAE INFRA-1 — Market Open Auto-Start Permission Fix & Reliability Audit

**Date:** 2026-07-01  
**Sprint:** INFRA-1  
**Scope:** Infrastructure only — trading logic untouched

---

## 1. Confirmed root cause

`market_open_runner.log` contains:

```
/bin/bash: /Users/book/Desktop/trading_ai/market_open_runner.sh: Operation not permitted
```

Crontab **did fire** at 09:50 (Mon–Fri), but **macOS blocked execution** of the shell script from cron/bash context. This is **not** a trading logic failure — `live_bot.py` runs fine when started manually.

Likely causes (macOS TCC):

- Cron lacks permission to execute scripts under `~/Desktop/`
- LaunchAgent `com.tradingai.startup` last exit **126** (permission denied) — same class of issue
- `com.apple.provenance` on all infra scripts (informational, not quarantine)

Awake Guard (`caffeinate` PID active) was **not** the blocker — Mac was awake-capable, but market open runner never ran.

---

## 2. Permission / attribute audit

| Script | Mode | Owner | Extended attributes |
|--------|------|-------|---------------------|
| `market_open_runner.sh` | `-rwxr-xr-x` | book:staff | `com.apple.provenance` |
| `market_close_runner.sh` | `-rwxr-xr-x` | book:staff | `com.apple.provenance` |
| `startup_runner.sh` | `-rwxr-xr-x` | book:staff | `com.apple.provenance` |
| `awake_guard.sh` | `-rwxr-xr-x` | book:staff | `com.apple.provenance` |

- **`com.apple.quarantine`:** NOT present — not removed (per policy)
- **`com.apple.provenance`:** present on all four scripts — reported as WARN only

---

## 3. Repairs applied

| Action | Result |
|--------|--------|
| `chmod +x` on all four scripts | Already executable; re-applied safely |
| Remove quarantine | Skipped — quarantine not present |
| `bash -n` syntax check | **PASS** all scripts |
| Duplicate bot guard in `market_open_runner.sh` | **Added** `pgrep -f live_bot.py` / dashboard skip before start |

### `market_open_runner.sh` patch (minimal)

Before calling `bot_controller.start_bot()` / `start_dashboard()`:

- If `pgrep -f "live_bot.py"` → log `SKIP: already running`
- If `pgrep -f "streamlit run dashboard_v2.py"` → log `SKIP: dashboard already running`

`bot_controller.py` already guards via PID file; pgrep adds defense when PID file is stale.

**Not run:** full `market_open_runner.sh` live execution (bot already active — avoided duplicate start).

---

## 4. Infrastructure inventory

### Crontab (verified present)

| Schedule | Job |
|----------|-----|
| `50 9 * * 1-5` | `market_open_runner.sh` |
| `15 23 * * 1-5` | `market_close_runner.sh` |
| `@reboot` | `startup_runner.sh` |
| `*/5 * * * 1-5` | `market_session_guard.py` |
| `*/30 * * * 1-5` | `tae_scanner_refresh.sh` |

### LaunchAgents

| Label | Status at audit |
|-------|-----------------|
| `com.tradingai.startup` | Loaded, **last_exit=126** (FAIL) |
| `com.tradingai.market-session-guard` | Loaded, exit 0 |

### Processes at audit

| Process | Count |
|---------|-------|
| `caffeinate -d -i -m` | 1 (Awake Guard active) |
| `live_bot.py` | 1 |
| `streamlit dashboard_v2.py` | 1 |

---

## 5. Health checker created

**Module:** `tae_infrastructure_health.py`

**Outputs:** `tae_infrastructure_health.json`, `tae_infrastructure_health.md`

**Checks:** script existence, executable bit, quarantine/provenance, bash syntax, crontab entries, LaunchAgents, caffeinate, bot/dashboard process count, venv python, runtime_outputs, `market_open_runner.log` errors.

### Live run result (2026-07-01)

| Metric | Value |
|--------|-------|
| Overall | **FAIL** |
| Autostart readiness | **NOT_READY** |
| PASS / WARN / FAIL | 22 / 4 / 2 |

**FAIL items:**

1. `launchagent:com.tradingai.startup` — exit 126 permission failure
2. `market_open_runner_log` — Operation not permitted

**WARN items:** `com.apple.provenance` on all four scripts (4×)

---

## 6. Recommended remediation (manual — outside code)

1. **Prefer LaunchAgent over cron** for `market_open_runner.sh` (launchd runs in user session with better TCC context)
2. **System Settings → Privacy & Security → Full Disk Access** — add `/usr/sbin/cron` or migrate jobs to LaunchAgents
3. **Alternative:** move project out of `Desktop/` (TCC-protected location)
4. **Reload startup LaunchAgent** after fixing permissions:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.tradingai.startup.plist
   launchctl load ~/Library/LaunchAgents/com.tradingai.startup.plist
   ```
5. Run before market open:
   ```bash
   python3 tae_infrastructure_health.py
   ```

---

## 7. Tests run

```bash
python3 -m py_compile tae_infrastructure_health.py   ✅
python3 tae_infrastructure_health_test.py               ✅ 8/8
python3 tae_infrastructure_health.py                    ✅ (exit 1 = FAIL detected correctly)
bash -n market_open_runner.sh ... awake_guard.sh      ✅
```

---

## 8. Confirmations

| Check | Status |
|-------|--------|
| `live_bot.py` modified | **NO** |
| BUY/SELL/Risk/Broker/Trading logic | **NO** |
| Market Data Layer | **NO** |
| Strategies / thresholds | **NO** |
| Git commit | **NO** |

---

## 9. Files created / modified

| File | Change |
|------|--------|
| `market_open_runner.sh` | pgrep duplicate guard (infra only) |
| `tae_infrastructure_health.py` | **Created** |
| `tae_infrastructure_health_test.py` | **Created** |
| `tae_infrastructure_health.json` | Generated |
| `tae_infrastructure_health.md` | Generated |

---

*TAE INFRA-1 — autostart reliability audit. Root cause: macOS Operation not permitted, not trading logic.*
