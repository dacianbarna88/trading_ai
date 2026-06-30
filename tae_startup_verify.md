# TAE Startup Verify

**Verdict:** PASS
**Startup command works:** True

## Results

- All markets closed: **True**
- Bot stopped expected: **True**
- Bot expected/actual: **STOPPED** / **STOPPED**
- Dashboard actual: **RUNNING**
- DRY_RUN live mode: **True** (source=default_live)
- Monitor verdict: **WAITING_FOR_MARKET_OPEN**
- Ecosystem verdict: **None**

**Next action:** All markets closed — bot STOPPED is expected. Wait for market open.

## Exit codes

- startup_runner: 0
- market_open_monitor: 0
- ecosystem_review: 0

## Sleep / Wake Readiness

- launchagent_repo_present: True
- launchagent_installed: True
- launchagent_installed_path: /Users/book/Library/LaunchAgents/com.tradingai.startup.plist
- run_at_load: True
- cron_has_market_guard: True
- startup_runner_executable: True
- awake_guard_executable: True
- market_guard_executable: True
- last_startup_runner_time: Tue Jun 30 03:02:13 EEST 2026
- last_startup_runner_age_hours: 0.0
- last_session_guard_time: 2026-06-30 03:02:15
- last_session_guard_age_hours: 0.0
- verdict: READY
- note: Sleep/wake cannot be simulated; chain checks LaunchAgent, executables, and recent startup/guard log timestamps.
