# TAE Market Open Monitor

**Verdict:** PASS
**Generated:** 2026-06-30T10:58:30.027948+00:00

## Summary

- Market open: **['EU', 'UK']**
- Bot: **RUNNING** (pid=16525, alive=False)
- Dashboard: **RUNNING** (port8501=True)
- DRY_RUN live mode: **True** (source=default_live)
- Session guard last run: 2026-06-30 13:56:47
- Startup runner last run: Tue Jun 30 10:55:14 EEST 2026

## Q&A

- **1_system_started_after_wake**: True
- **2_startup_runner_ran**: True
- **3_market_session_guard_ran**: True
- **4_dry_run_false**: True
- **5_market_open_checks**: {'bot_started': True, 'dashboard_started': True, 'pid_alive': False, 'bot_output_recent': True, 'live_signals_recent': True, 'x9_recent': True}
- **6_all_markets_closed**: {'stopped_expected': False, 'readiness_ready': True}
- **7_dashboard_without_bot_explanation**: None
- **8_bot_fail_if_open_and_stopped**: False
- **9_bot_running_no_signals_warning**: False
- **10_x9_empty_before_open_ok**: False
- **11_x9_empty_after_buy_eval_warning**: False

## Sleep / Wake Readiness

- launchagent_repo_present: True
- launchagent_startup_installed: True
- launchagent_guard_installed: True
- launchagent_guard_start_interval_seconds: 300
- launchagent_installed_path: /Users/book/Library/LaunchAgents/com.tradingai.startup.plist
- run_at_load: True
- cron_has_market_guard: None
- startup_runner_executable: True
- awake_guard_executable: True
- market_guard_executable: True
- last_startup_runner_time: Tue Jun 30 10:55:14 EEST 2026
- last_startup_runner_age_hours: 3.05
- last_session_guard_time: 2026-06-30 13:56:47
- last_session_guard_age_hours: 0.03
- verdict: READY
- note: Sleep/wake cannot be simulated; chain checks LaunchAgent, executables, and recent startup/guard log timestamps.
