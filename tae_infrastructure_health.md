# TAE Infrastructure Health

**Generated:** 2026-07-05T20:44:11
**Overall:** PASS
**Autostart readiness:** READY

## Summary
- PASS: 38
- INFO: 4
- WARN: 0
- FAIL: 0

## Checks
- **PASS** `script_exists:market_open_runner.sh` — market_open_runner.sh present
- **PASS** `script_executable:market_open_runner.sh` — market_open_runner.sh executable
- **INFO** `provenance:market_open_runner.sh` — com.apple.provenance present — normal on macOS; not a blocker when scripts are executable and launchd last_exit=0
- **PASS** `bash_syntax:market_open_runner.sh` — market_open_runner.sh bash -n OK
- **PASS** `script_exists:market_close_runner.sh` — market_close_runner.sh present
- **PASS** `script_executable:market_close_runner.sh` — market_close_runner.sh executable
- **INFO** `provenance:market_close_runner.sh` — com.apple.provenance present — normal on macOS; not a blocker when scripts are executable and launchd last_exit=0
- **PASS** `bash_syntax:market_close_runner.sh` — market_close_runner.sh bash -n OK
- **PASS** `script_exists:startup_runner.sh` — startup_runner.sh present
- **PASS** `script_executable:startup_runner.sh` — startup_runner.sh executable
- **INFO** `provenance:startup_runner.sh` — com.apple.provenance present — normal on macOS; not a blocker when scripts are executable and launchd last_exit=0
- **PASS** `bash_syntax:startup_runner.sh` — startup_runner.sh bash -n OK
- **PASS** `script_exists:awake_guard.sh` — awake_guard.sh present
- **PASS** `script_executable:awake_guard.sh` — awake_guard.sh executable
- **INFO** `provenance:awake_guard.sh` — com.apple.provenance present — normal on macOS; not a blocker when scripts are executable and launchd last_exit=0
- **PASS** `bash_syntax:awake_guard.sh` — awake_guard.sh bash -n OK
- **PASS** `cron:market_close_runner\.sh` — Crontab entry found
- **PASS** `cron:market_session_guard\.py` — Crontab entry found
- **PASS** `cron:daily_intelligence` — Crontab entry found
- **PASS** `cron_duplicate:market_open_runner\.sh` — No duplicate cron for market_open_runner\.sh
- **PASS** `cron_duplicate:startup_runner\.sh` — No duplicate cron for startup_runner\.sh
- **PASS** `plist_lint:com.tradingai.startup` — plutil OK: /Users/book/Desktop/trading_ai/launchagents/com.tradingai.startup.plist
- **PASS** `plist_program:com.tradingai.startup` — ProgramArguments set: /Users/book/Desktop/trading_ai/venv/bin/python3
- **PASS** `plist_workdir:com.tradingai.startup` — WorkingDirectory=/Users/book/Desktop/trading_ai
- **PASS** `plist_lint:com.tradingai.market-open` — plutil OK: /Users/book/Desktop/trading_ai/launchagents/com.tradingai.market-open.plist
- **PASS** `plist_bash:com.tradingai.market-open` — ProgramArguments uses /bin/bash
- **PASS** `plist_workdir:com.tradingai.market-open` — WorkingDirectory=/Users/book/Desktop/trading_ai
- **PASS** `plist_lint:com.tradingai.market-session-guard` — plutil OK: /Users/book/Desktop/trading_ai/launchagents/com.tradingai.market-session-guard.plist
- **PASS** `plist_program:com.tradingai.market-session-guard` — ProgramArguments set: /Users/book/Desktop/trading_ai/venv/bin/python3
- **PASS** `plist_workdir:com.tradingai.market-session-guard` — WorkingDirectory=/Users/book/Desktop/trading_ai
- **PASS** `launchagent:com.tradingai.startup` — com.tradingai.startup loaded (pid=- last_exit=0)
- **PASS** `launchagent:com.tradingai.market-open` — com.tradingai.market-open loaded (pid=- last_exit=78)
- **PASS** `launchagent:com.tradingai.market-session-guard` — com.tradingai.market-session-guard loaded (pid=- last_exit=0)
- **PASS** `awake_guard_caffeinate` — caffeinate processes=1
- **PASS** `live_bot_process` — live_bot.py running (1)
- **PASS** `dashboard_process` — dashboard running (1)
- **PASS** `runtime_outputs` — runtime_outputs exists
- **PASS** `venv_python` — /Users/book/Desktop/trading_ai/venv/bin/python3
- **PASS** `startup_launchagent_log` — Logs OK; last_out=empty
- **PASS** `startup_runner_log` — Recent python launcher startup recorded in startup_runner.log
- **PASS** `market_open_launchagent_log` — Logs OK; last_out=empty
- **PASS** `market_open_runner_log_legacy` — No legacy cron blockers in market_open_runner.log
