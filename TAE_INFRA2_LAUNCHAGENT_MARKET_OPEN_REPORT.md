# TAE INFRA-2 — LaunchAgent Market Open Runner Migration Report

**Date:** 2026-07-02  
**Sprint:** INFRA-2  
**Scope:** Infrastructure only — trading logic untouched

---

## 1. Objective

Migrate `market_open_runner.sh` from **cron** (blocked by macOS `Operation not permitted`) to a dedicated **LaunchAgent** running Mon–Fri at **09:50 local**.

---

## 2. Root cause (from INFRA-1)

Cron attempted execution; macOS TCC blocked bash from running Desktop scripts. LaunchAgents run in the **user GUI domain** with better permission context.

---

## 3. Created / installed

### Plist (repo + LaunchAgents)

| Location | Status |
|----------|--------|
| `launchagents/com.tradingai.market-open.plist` | **Created** |
| `~/Library/LaunchAgents/com.tradingai.market-open.plist` | **Installed** |

### Schedule

- **Label:** `com.tradingai.market-open`
- **When:** Monday–Friday, 09:50 local (`StartCalendarInterval` × 5)
- **Command:** `/bin/bash /Users/book/Desktop/trading_ai/market_open_runner.sh`
- **RunAtLoad:** `false` (schedule only)

### Logs

| File | Purpose |
|------|---------|
| `market_open_launchagent.out.log` | stdout |
| `market_open_launchagent.err.log` | stderr |

### Anti-duplicate guard

Already present in `market_open_runner.sh` (INFRA-1):

- `pgrep -f "live_bot.py"` → skip bot start
- `pgrep -f "streamlit run dashboard_v2.py"` → skip dashboard start

Plus `bot_controller.py` PID-file guards.

---

## 4. Installation commands run

```bash
plutil -lint launchagents/com.tradingai.market-open.plist   # OK
cp launchagents/com.tradingai.market-open.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.tradingai.market-open.plist
```

### LaunchAgent status

```
launchctl list | grep tradingai
-  0  com.tradingai.market-open          ✅ loaded, last_exit=0
-  126 com.tradingai.startup             ⚠️ permission issue (separate)
-  0  com.tradingai.market-session-guard ✅
```

---

## 5. Cron migration

**Removed** (verified):

```
50 9 * * 1-5 ... market_open_runner.sh   ← REMOVED
```

**Remaining crontab** (unchanged):

- `market_session_guard.py` every 5 min (Mon–Fri)
- `market_close_runner.sh` 23:15 (Mon–Fri)
- `startup_runner.sh` @reboot
- `daily_intelligence_runner.py`, `tae_scanner_refresh.sh`

Health checker now **WARNs** if `market_open_runner.sh` reappears in crontab (duplicate risk).

---

## 6. Health checker updates

`tae_infrastructure_health.py` now verifies:

| Check | Description |
|-------|-------------|
| `com.tradingai.market-open` | LaunchAgent loaded |
| `market_open_plist` | Plist exists + `plutil -lint` |
| `cron_duplicate:market_open_runner` | WARN if cron line still present |
| `market_open_launchagent_log` | Last LaunchAgent out/err logs |
| Removed | `market_open_runner` from **required** cron patterns |

---

## 7. Live health run (post-migration)

| Metric | Value |
|--------|-------|
| Overall | **FAIL** (legacy issues remain) |
| PASS / WARN / FAIL | 24 / 5 / 2 |

**Remaining FAIL (not blocking new LaunchAgent):**

1. `com.tradingai.startup` exit **126** — login startup agent still permission-blocked
2. `market_open_runner.log` — **historical** cron `Operation not permitted` lines (clears after next successful LaunchAgent run)

**New checks PASS:**

- `com.tradingai.market-open` loaded
- `market_open_plist` lint OK
- `cron_duplicate:market_open_runner` — no duplicate

---

## 8. Tests run

```bash
python3 -m py_compile tae_infrastructure_health.py tae_infrastructure_health_test.py  ✅
python3 tae_infrastructure_health_test.py                                         ✅ 9/9
python3 tae_infrastructure_health.py                                                ✅ (exit 1 = legacy FAILs)
plutil -lint launchagents/com.tradingai.market-open.plist                           ✅
launchctl list | grep tradingai                                                     ✅ market-open loaded
```

---

## 9. Confirmations

| Check | Status |
|-------|--------|
| `live_bot.py` modified | **NO** |
| BUY/SELL/Risk/Broker/Trading | **NO** |
| Market Data Layer | **NO** |
| Cron duplicate risk | **Mitigated** — cron line removed + health WARN |
| LaunchAgent `com.tradingai.market-open` | **Loaded (exit 0)** |
| Git commit | **NO** |

---

## 10. Next steps

1. **Monday 09:50** — verify first scheduled LaunchAgent run in `market_open_launchagent.out.log`
2. Fix **`com.tradingai.startup`** exit 126 (Full Disk Access / plist review)
3. After successful run, old `market_open_runner.log` errors become historical only
4. Optional: `launchctl print gui/$(id -u)/com.tradingai.market-open` for schedule confirmation

---

*TAE INFRA-2 — market open migrated from cron to LaunchAgent.*
