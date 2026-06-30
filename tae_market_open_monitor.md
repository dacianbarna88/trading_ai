# TAE Market Open Monitor

**Verdict:** WAITING_FOR_MARKET_OPEN
**Generated:** 2026-06-30T00:02:19.041578+00:00

## Summary

- Market open: **[]**
- Bot: **STOPPED** (pid=None, alive=False)
- Dashboard: **RUNNING** (port8501=True)
- DRY_RUN live mode: **True** (source=default_live)
- Session guard last run: 2026-06-30 03:02:15
- Startup runner last run: Tue Jun 30 03:02:13 EEST 2026

## Q&A

- **1_system_started_after_wake**: True
- **2_startup_runner_ran**: True
- **3_market_session_guard_ran**: True
- **4_dry_run_false**: True
- **5_market_open_checks**: {'bot_started': None, 'dashboard_started': None, 'pid_alive': None, 'bot_output_recent': None, 'live_signals_recent': None, 'x9_recent': None}
- **6_all_markets_closed**: {'stopped_expected': True, 'readiness_ready': True}
- **7_dashboard_without_bot_explanation**: all markets closed — bot start skipped by session guard; last guard START_REASON=all_markets_closed; guard did not attempt bot start
- **8_bot_fail_if_open_and_stopped**: False
- **9_bot_running_no_signals_warning**: False
- **10_x9_empty_before_open_ok**: True
- **11_x9_empty_after_buy_eval_warning**: False

## Notes

- All markets closed — bot STOPPED expected.

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
