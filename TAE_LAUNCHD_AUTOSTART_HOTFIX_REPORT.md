# TAE LaunchAgent Autostart Hotfix Report

**Date:** 2026-07-07  
**Sprint:** P0 HOTFIX — macOS LaunchAgent market-open autostart  
**Mode:** Infrastructure only · NO trading/DPE/live SSOT changes · NO commit unless validation PASS

---

## Problem

Installed `~/Library/LaunchAgents/com.tradingai.market-open.plist` invoked:

```text
venv/bin/python3 → bot_controller.py start
```

launchd failed **before Python started**:

```text
posix_spawn(.../venv/bin/python3), error 0x1 — Operation not permitted
last exit code = 78 (EX_CONFIG)
```

`market_open_launchagent.out.log` / `.err.log` remained empty.

---

## Root cause

| Issue | Detail |
|-------|--------|
| **venv python from launchd** | macOS TCC blocks `venv/bin/python3` as LaunchAgent executable on Desktop project |
| **Prior broken plist** | Installed plist differed from repo template (venv direct call) |
| **Desktop `.sh` under launchd** | `/bin/bash` + Desktop `.sh` also fails with **exit 126** (Operation not permitted) |

Validated:

```text
bash + tae_launchd_market_open_safe.sh        → exit 126 under launchd
bash + ~/.local/bin/symlink → same target     → exit 126
framework python + tae_launchd_market_open_safe.py → exit 0 ✅
```

Manual operator runs work; **launchd requires framework Python entry**, not venv or Desktop bash script execution.

---

## Fix applied

### 1. `tae_launchd_market_open_safe.sh` (manual / diagnostics)

- `/bin/bash` launcher for operator validation
- Uses **framework Python** (`/Library/Frameworks/Python.framework/Versions/3.14/bin/python3`), not venv
- Explicit logging to `tae_launchd_market_open_safe.log` / `.err.log`
- Diagnostics: whoami, pwd, python path, xattr, exit codes, pgrep status
- Starts bot + dashboard via `bot_controller.py start --force` (scheduled launchd)
- **Does not** call `market_open_runner.sh` (uses venv internally)
- Optional intelligence stack non-fatal (framework python)
- Anti-duplicate pgrep filtering

### 2. `tae_launchd_market_open_safe.py` (launchd production entry)

- Same logic as shell launcher, Python-native for launchd
- Invoked by framework Python from plist (proven pattern, same class as session-guard)

### 3. Repaired `launchagents/com.tradingai.market-open.plist`

**Production ProgramArguments:**

```xml
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
/Users/book/Desktop/trading_ai/tae_launchd_market_open_safe.py
```

- **Not** venv python
- WorkingDirectory set
- `TAE_SCHEDULER_SOURCE=launchd`
- Logs → `tae_launchd_market_open_safe.log` / `.err.log`
- Schedule: Mon–Fri 09:50 local

Installed to: `~/Library/LaunchAgents/com.tradingai.market-open.plist`

---

## Validation results

```bash
plutil -lint ~/Library/LaunchAgents/com.tradingai.market-open.plist
# OK

launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.tradingai.market-open.plist || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.tradingai.market-open.plist
launchctl kickstart -k gui/$(id -u)/com.tradingai.market-open
```

| Check | Result |
|-------|--------|
| last exit code | **0** ✅ |
| Logs non-empty | **yes** ✅ |
| live_bot.py running | **yes** (single instance) ✅ |
| dashboard running | **yes** (port 8501) ✅ |
| duplicate live_bot | **no** ✅ |
| EX_CONFIG | **resolved** ✅ |

Sample log tail:

```text
RESULT: PASS — bot and dashboard running
post_run bot_count=1 dashboard_count=1
bot_status.txt=RUNNING
dashboard_status.txt=RUNNING
```

---

## Operator commands

### Reinstall plist after git pull

```bash
cp launchagents/com.tradingai.market-open.plist ~/Library/LaunchAgents/
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.tradingai.market-open.plist 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.tradingai.market-open.plist
```

### Manual test (without launchd)

```bash
/bin/bash /Users/book/Desktop/trading_ai/tae_launchd_market_open_safe.sh
```

### Force launchd test

```bash
launchctl kickstart -k gui/$(id -u)/com.tradingai.market-open
tail -100 tae_launchd_market_open_safe.log
```

---

## Files changed (infrastructure only)

| File | Role |
|------|------|
| `tae_launchd_market_open_safe.sh` | Manual/bash diagnostic launcher |
| `tae_launchd_market_open_safe.py` | launchd production entry |
| `launchagents/com.tradingai.market-open.plist` | Repaired agent definition |
| `TAE_LAUNCHD_AUTOSTART_HOTFIX_REPORT.md` | This report |

**Not modified:** `live_bot.py`, `portfolio.csv`, `live_signals.csv`, `watchlist.txt`, `core/`, DPE modules, trading logic.

---

## Notes

1. **Intelligence runner** may exit non-zero (non-fatal) — bot/dashboard autostart still PASS.
2. **Duplicate bot cleanup:** if `pgrep -fl live_bot.py` shows >1 instance, stop extras manually before Monday schedule.
3. **Future:** if project moves off Desktop, bash-only plist may work; until then use framework Python entry.

---

## Safety confirmation

| Rule | Status |
|------|--------|
| NO trading logic change | ✅ |
| NO DPE logic change | ✅ |
| NO live SSOT change | ✅ |
| NO broker | ✅ |
| Validation PASS | ✅ |
