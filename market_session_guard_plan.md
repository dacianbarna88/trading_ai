# Trading AI — Phase 1: Market Session Guard

**Status:** Plan only — no implementation yet  
**Date:** 2026-06-23  
**Scope:** Operational session control and bot watchdog only

---

## 1. Goal

Ensure the Trading AI bot process is **RUNNING** whenever **any** of these markets is open:

| Market | Config source | Exchange timezone | Current configured hours |
|--------|---------------|-------------------|--------------------------|
| Europe | `markets/market_config.py` → `EU` | `Europe/Berlin` | 09:00–17:30 Mon–Fri |
| UK | `markets/market_config.py` → `UK` | `Europe/London` | 08:00–16:30 Mon–Fri |
| US | `markets/market_config.py` → `US` | `US/Eastern` | 16:30–23:00 Mon–Fri |

**Union rule (single source of truth):**

```
any_market_open() = is_market_open("EU") OR is_market_open("UK") OR is_market_open("US")
```

All checks must go through `markets/market_config.py` + `markets/market_hours.py`. No duplicate session windows in the guard.

---

## 2. Out of scope (must NOT change)

| Area | Reason |
|------|--------|
| Buy logic | Explicit requirement |
| Sell logic | Explicit requirement |
| `portfolio.csv` | Explicit requirement |
| V41 logic (`core/v41_shadow.py`, `v41_*`, `V41_SAFE_MODE`) | Explicit requirement |
| Risk logic (`core/risk.py`, trailing, stop-loss, regime sizing) | Explicit requirement |
| `live_bot.py` / `live_bot_v5_1.py` trading loops | Session guard only starts/stops process |
| Dashboard UI | Not required for Phase 1 |

The guard may call `bot_controller.start_bot()` and `bot_controller.get_status()` only. It must not import trade, portfolio, or signal modules.

---

## 3. Current state (read-only audit summary)

### 3.1 How the bot starts today

- **One daily cron trigger:** `50 9 * * 1-5` → `market_open_runner.sh` → `bot_controller.start_bot()`
- **`start_bot()` is idempotent:** if `bot_pid.txt` points to a live process, subsequent calls do nothing
- **No periodic watchdog:** if the bot crashes after 09:50, nothing restarts it until the next weekday 09:50
- **`market_close_runner.sh` does not stop the bot** — it kills `caffeinate` and runs `pmset sleepnow`

### 3.2 Active bot entrypoint

`bot_controller.py` starts `live_bot.py` (if present). The guard will use the existing controller without changing which script is launched in Phase 1.

### 3.3 Known config inconsistency (pre-existing)

`markets/market_config.py` US hours are stored as `16:30–23:00` in `US/Eastern`. Real US cash session is ~`09:30–16:00` Eastern. The naive-local windows elsewhere in the repo (`core/market_hours.py` at 16:30–23:00 local) suggest the **intent** was local-machine time for a Romania-based Mac, but the timezone-aware US entry is misaligned.

**Phase 1 recommendation:** fix US hours in `market_config.py` to real exchange times (`open 9:30`, `close 16:00`, `US/Eastern`) as part of making `markets/market_config.py` the authoritative source. This is **session definition**, not buy/sell logic. Document and validate before enabling the guard cron.

---

## 4. Target architecture

```
┌─────────────────────────────────────────────────────────────┐
│  cron (every 10 min, Mon–Fri)                               │
│       │                                                     │
│       ▼                                                     │
│  market_session_guard.sh                                    │
│       │                                                     │
│       ▼                                                     │
│  market_session_guard.py                                    │
│       │                                                     │
│       ├── markets/market_hours.py  → any_market_open()      │
│       ├── bot_controller.get_status()                       │
│       └── bot_controller.start_bot()  (if needed)           │
│                                                             │
│  Logs → market_session_guard.log                            │
└─────────────────────────────────────────────────────────────┘
```

**Decision table (every run):**

| `any_market_open()` | `get_status()` | Action |
|---------------------|----------------|--------|
| `True` | `RUNNING` | Log OK, no action |
| `True` | `STOPPED` | Call `start_bot()`, log restart |
| `False` | `RUNNING` | Log only — do **not** stop bot in Phase 1 |
| `False` | `STOPPED` | Log only — no restart (requirement) |

**Optional Phase 1 addition (recommended, operational only):** if `any_market_open()` is `True`, invoke `awake_guard.sh` so cron can fire while Mac would otherwise sleep. Does not touch trading logic.

---

## 5. Files to create

### 5.1 `market_session_guard.py` (new)

**Purpose:** Session-aware bot watchdog.

**Responsibilities:**

1. Resolve project root (same directory as script or `PROJECT_DIR` env override)
2. Import from `markets/market_hours`:
   - `get_market_statuses()` (existing)
   - `any_market_open()` (to be added — see §6)
3. Import from `bot_controller`:
   - `get_status()`
   - `start_bot()`
4. Run decision table (§4)
5. Append structured lines to `market_session_guard.log`

**Suggested log line format:**

```
[2026-06-23 10:10:02] OPEN=[EU,UK] CLOSED=[US] BOT=STOPPED ACTION=START result="Bot pornit: live_bot.py"
[2026-06-23 10:20:01] OPEN=[EU,UK] CLOSED=[US] BOT=RUNNING ACTION=NONE
[2026-06-23 23:10:00] OPEN=[] CLOSED=[EU,UK,US] BOT=RUNNING ACTION=NONE
```

**Implementation constraints:**

- No edits to `portfolio.csv`, signal files, or trade modules
- Use `if __name__ == "__main__"` entrypoint returning exit code `0` on success, `1` on unexpected exception
- Catch and log exceptions; never leave cron silent
- Support `DRY_RUN=1` env var for Phase 0 validation (log actions without calling `start_bot()`)

**Pseudocode:**

```python
def main():
    statuses = get_market_statuses()
    any_open = any_market_open()
    bot_status = get_status()
    open_names = [k for k, v in statuses.items() if v]
    closed_names = [k for k, v in statuses.items() if not v]

    action = "NONE"
    result = ""

    if any_open and bot_status != "RUNNING":
        action = "START"
        if not dry_run:
            result = start_bot()
            bot_status = get_status()
        else:
            result = "DRY_RUN would start bot"

    log_line(open_names, closed_names, bot_status, action, result)

    if any_open and ensure_awake:
        run_awake_guard()  # optional, see §5.2
```

### 5.2 `market_session_guard.sh` (new)

**Purpose:** Cron-safe wrapper.

**Contents (spec):**

```bash
#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/book/Desktop/trading_ai"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python3"
LOG_FILE="$PROJECT_DIR/market_session_guard.log"

cd "$PROJECT_DIR" || exit 1

# Optional: ensure Mac stays awake during market hours
# /bin/bash "$PROJECT_DIR/awake_guard.sh" >> "$LOG_FILE" 2>&1

"$PYTHON_BIN" "$PROJECT_DIR/market_session_guard.py" >> "$LOG_FILE" 2>&1
```

**Requirements:**

- `chmod +x market_session_guard.sh`
- Use venv Python (consistent with `crontab_fixed.txt`)
- Append-only logging (cron must not truncate history)

### 5.3 `market_session_guard_plan.md` (this document)

Planning artifact for review before any code changes.

---

## 6. Files to modify

### 6.1 `markets/market_hours.py` — **required, minimal**

Add two functions; do not change existing `is_market_open()` behavior (other modules depend on it):

```python
def any_market_open():
    return any(
        is_market_open(name)
        for name in MARKETS
        if MARKETS[name].get("enabled", False)
    )

def get_open_markets():
    return [name for name in MARKETS if is_market_open(name)]
```

This keeps `markets/market_config.py` + `markets/market_hours.py` as the **only** session truth for the guard.

### 6.2 `markets/market_config.py` — **recommended before go-live**

Correct US session to real exchange hours:

```python
"open_hour": 9,
"open_minute": 30,
"close_hour": 16,
"close_minute": 0,
```

Validate with:

```bash
cd /Users/book/Desktop/trading_ai
venv/bin/python3 markets/market_hours.py
```

Run at known EU open, UK open, and US open times. Document results in `market_session_guard.log` during dry-run.

**Risk if skipped:** guard may never detect US as open (current misconfigured window) or detect it at wrong times.

### 6.3 `crontab_fixed.txt` — **required at install time**

Add the 10-minute guard entry (see §8). Keep existing lines during parallel-run period.

### 6.4 `install_market_day_schedule.sh` — **optional but recommended**

Update the heredoc to include the guard cron line so reinstalling the schedule does not drop the watchdog.

### 6.5 Files explicitly NOT modified in Phase 1

| File | Why leave unchanged |
|------|---------------------|
| `bot_controller.py` | Existing `start_bot()` / `get_status()` sufficient |
| `live_bot.py`, `live_bot_v5_1.py` | Trading logic out of scope |
| `market_open_runner.sh` | Keep as morning bootstrap during parallel period |
| `market_close_runner.sh` | Sleep/backup unchanged in Phase 1 |
| `core/market_hours.py` | Not used by guard; unify in later phase |
| Any V41 / risk / portfolio modules | Out of scope |

---

## 7. Implementation sequence (when approved)

### Step 1 — Config validation (no cron)

1. Add `any_market_open()` to `markets/market_hours.py`
2. Fix US hours in `market_config.py` (if approved)
3. Manual test: `python3 markets/market_hours.py` at multiple times of day

### Step 2 — Guard script (dry-run)

1. Create `market_session_guard.py` with `DRY_RUN=1` default or env flag
2. Create `market_session_guard.sh`
3. Run manually: `DRY_RUN=1 ./market_session_guard.sh`
4. Verify log output against expected open/closed markets

### Step 3 — Live guard (manual, no cron)

1. Stop bot manually (`bot_controller.stop_bot()` or dashboard)
2. Run guard with `DRY_RUN=0` during an open session
3. Confirm bot starts and `bot_status.txt` = `RUNNING`
4. Kill bot PID, rerun guard, confirm restart

### Step 4 — Cron install (parallel with existing schedule)

1. Backup crontab: `crontab -l > crontab_backup_YYYYMMDD.txt`
2. Add `*/10 * * * 1-5` guard line
3. Keep existing `09:50` open runner and `23:15` close runner for 1 week
4. Monitor `market_session_guard.log` daily

### Step 5 — Retire redundancy (future phase, not Phase 1)

- Remove bot start from `market_open_runner.sh` once guard is proven
- Make `market_close_runner.sh` conditional on `not any_market_open()`

---

## 8. Exact cron entries

### 8.1 Proposed full crontab (`crontab_fixed.txt`)

```cron
# Trading AI — Market Session Guard (every 10 min, weekdays)
*/10 * * * 1-5 cd "/Users/book/Desktop/trading_ai" && /bin/bash /Users/book/Desktop/trading_ai/market_session_guard.sh

# Existing — keep during parallel-run period
*/30 * * * * cd "/Users/book/Desktop/trading_ai" && "/Users/book/Desktop/trading_ai/venv/bin/python3" daily_intelligence_runner.py >> scheduler_run.log 2>&1
50 9 * * 1-5 cd "/Users/book/Desktop/trading_ai" && /bin/bash /Users/book/Desktop/trading_ai/market_open_runner.sh >> market_open_runner.log 2>&1
15 23 * * 1-5 cd "/Users/book/Desktop/trading_ai" && /bin/bash /Users/book/Desktop/trading_ai/market_close_runner.sh >> market_close_runner.log 2>&1
```

### 8.2 Guard-only line (minimal add)

```cron
*/10 * * * 1-5 cd "/Users/book/Desktop/trading_ai" && /bin/bash /Users/book/Desktop/trading_ai/market_session_guard.sh
```

### 8.3 Cron design notes

| Setting | Value | Rationale |
|---------|-------|-----------|
| Interval | `*/10` | Requirement; balances recovery time vs overhead |
| Days | `1-5` Mon–Fri | Matches exchange weekday assumption in `is_market_open()` |
| Hours | `*` (all hours) | EU/UK open ~08:00–09:00 local; US ~16:30 local; guard must run before 09:50 |
| Shell | `/bin/bash` | Consistent with existing runners |
| Log | `market_session_guard.log` | Separate from `market_open_runner.log` |

**Mac sleep caveat:** cron does not run while the Mac is asleep. The guard complements (does not replace) existing `09:45` wake + `09:50` open runner + `awake_guard.sh`. Optional: call `awake_guard.sh` from the guard when `any_market_open()` is true.

---

## 9. Rollback plan

### 9.1 Immediate rollback (< 2 minutes)

```bash
# Restore previous crontab
crontab /Users/book/Desktop/trading_ai/crontab_backup_YYYYMMDD.txt

# Verify
crontab -l
```

### 9.2 Partial rollback (disable guard only)

Remove the `*/10` guard line from crontab; leave all other entries. No code deletion required.

### 9.3 Full rollback (remove Phase 1 artifacts)

1. Restore crontab from backup
2. Delete (optional):
   - `market_session_guard.py`
   - `market_session_guard.sh`
   - `market_session_guard.log`
3. Revert `markets/market_hours.py` if `any_market_open()` was added (single function block)
4. Revert `markets/market_config.py` US hours if changed

**Pre-install requirement:** always run `crontab -l > crontab_backup_$(date +%Y%m%d).txt` before installing.

### 9.4 Rollback validation

- Confirm `50 9 * * 1-5` open runner still present
- Confirm bot starts via manual `market_open_runner.sh` test
- Confirm no orphan guard processes: `ps aux | grep market_session_guard`

---

## 10. Risk assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| US hours misconfigured — guard never treats US as open | **High** | High (current state) | Fix `market_config.py` US times before go-live; validate with CLI |
| Restart loop — guard repeatedly starts bot that instantly crashes | Medium | Low | Log every start; alert on >3 starts in 30 min; inspect `bot_error.log` |
| Duplicate start race — guard and `market_open_runner.sh` at 09:50 | Low | Medium | `start_bot()` idempotent; harmless double-call |
| Cron silent failure — venv path wrong | Medium | Low | Use absolute paths; test wrapper manually once |
| Mac asleep — guard never runs | **High** | Medium | Keep `awake_guard.sh` + morning wake; optionally invoke awake guard from session guard |
| Guard starts bot outside intended script | Low | Low | Phase 1 does not change `bot_controller` script selection |
| Timezone / DST drift | Medium | Low | `zoneinfo` in `markets/market_hours.py` handles DST; log market statuses each run |
| False sense of security — bot RUNNING but not trading EU/UK morning | Medium | High (pre-existing) | Out of scope for Phase 1; document that `live_bot.py` buy gate is separate from process guard |
| Accidental scope creep into V41/risk/portfolio | Low | Low | Guard imports limited to `markets.*` and `bot_controller` only |

---

## 11. Success criteria

Phase 1 is complete when:

1. `market_session_guard.py` and `market_session_guard.sh` exist and run without error
2. `any_market_open()` is defined in `markets/market_hours.py`
3. During any open EU/UK/US session, if bot is stopped or crashed, guard restarts it within **10 minutes**
4. When all markets closed, guard logs status and does **not** restart a stopped bot
5. `market_session_guard.log` shows open markets, bot status, and action on every run
6. No changes to buy logic, sell logic, `portfolio.csv`, V41, or risk modules
7. Crontab includes `*/10 * * * 1-5` guard entry

---

## 12. Testing checklist (post-implementation)

- [ ] `python3 markets/market_hours.py` prints correct OPEN/CLOSED per market
- [ ] `any_market_open()` returns `True` when at least one market is open
- [ ] Manual: bot stopped + market open → guard starts bot
- [ ] Manual: kill bot PID + market open → guard restarts within one run
- [ ] Manual: all markets closed + bot stopped → guard does not start
- [ ] Manual: `DRY_RUN=1` produces log lines without starting bot
- [ ] Cron: verify entry in `crontab -l`
- [ ] After 24h: review `market_session_guard.log` for unexpected START loops
- [ ] Confirm `portfolio.csv` timestamp unchanged by guard runs

---

## 13. File change summary

| Action | Path |
|--------|------|
| **Create** | `market_session_guard.py` |
| **Create** | `market_session_guard.sh` |
| **Create** | `market_session_guard_plan.md` (this file) |
| **Create** | `market_session_guard.log` (runtime, append-only) |
| **Modify** | `markets/market_hours.py` — add `any_market_open()`, `get_open_markets()` |
| **Modify (recommended)** | `markets/market_config.py` — fix US exchange hours |
| **Modify (at install)** | `crontab_fixed.txt` — add 10-min guard line |
| **Modify (optional)** | `install_market_day_schedule.sh` — include guard in installer |
| **Do not modify** | Buy/sell, portfolio, V41, risk, `live_bot*.py` trading logic |

---

## 14. Approval gate

**Do not implement until:**

1. US hours correction in `market_config.py` is reviewed and approved
2. Parallel-run period with existing `09:50` open runner is accepted
3. Optional `awake_guard.sh` integration from guard is decided (recommended: yes)
4. Crontab backup procedure is confirmed

Once approved, implementation order: §6.1 → §5.1 → §5.2 → §7 Step 3 → §8 cron install.
