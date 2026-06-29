import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
LOG_FILE = PROJECT_DIR / "market_session_guard.log"
AWAKE_GUARD_SCRIPT = PROJECT_DIR / "awake_guard.sh"


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    with open(LOG_FILE, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def is_dry_run():
    return os.getenv("DRY_RUN", "").strip() == "1"


def ensure_awake_guard():
    if not AWAKE_GUARD_SCRIPT.exists():
        log(f"ACTION=AWAKE_GUARD SKIPPED reason=missing script path={AWAKE_GUARD_SCRIPT}")
        return "missing script"

    if is_dry_run():
        return "DRY_RUN would run awake_guard.sh"

    result = subprocess.run(
        ["/bin/bash", str(AWAKE_GUARD_SCRIPT)],
        cwd=str(PROJECT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        log(f"ACTION=AWAKE_GUARD ERROR code={result.returncode} stderr={stderr}")
        return f"error code={result.returncode}"

    return "awake_guard invoked"


def main():
    os.chdir(PROJECT_DIR)
    sys.path.insert(0, str(PROJECT_DIR))

    from bot_controller import get_dashboard_status, get_status, start_bot, start_dashboard
    from markets.market_hours import any_market_open, get_market_statuses, get_open_markets

    dry_run = is_dry_run()
    statuses = get_market_statuses()
    open_markets = get_open_markets()
    closed_markets = [name for name, is_open in statuses.items() if not is_open]
    markets_open = any_market_open()
    bot_status = get_status()
    dashboard_status = get_dashboard_status()

    bot_action = "NONE"
    dashboard_action = "NONE"
    bot_result = ""
    dashboard_result = ""
    awake_result = ""
    start_reason = "NONE"

    if markets_open:
        start_reason = "market_session_open"
        awake_result = ensure_awake_guard()

        if bot_status != "RUNNING":
            bot_action = "START"
            if dry_run:
                bot_result = "DRY_RUN would start bot"
            else:
                bot_result = start_bot()
                bot_status = get_status()

        if dashboard_status != "RUNNING":
            dashboard_action = "START"
            if dry_run:
                dashboard_result = "DRY_RUN would start dashboard"
            else:
                dashboard_result = start_dashboard()
                dashboard_status = get_dashboard_status()
    else:
        start_reason = "all_markets_closed"

    log(
        "OPEN=[{open}] CLOSED=[{closed}] BOT={bot} DASHBOARD={dashboard} "
        "BOT_ACTION={bot_action} DASHBOARD_ACTION={dashboard_action} "
        "START_REASON={start_reason} AWAKE={awake} BOT_RESULT={bot_result} "
        "DASHBOARD_RESULT={dashboard_result} DRY_RUN={dry_run}".format(
            open=",".join(open_markets) if open_markets else "NONE",
            closed=",".join(closed_markets) if closed_markets else "NONE",
            bot=bot_status,
            dashboard=dashboard_status,
            bot_action=bot_action,
            dashboard_action=dashboard_action,
            start_reason=start_reason,
            awake=awake_result or "NONE",
            bot_result=bot_result or "NONE",
            dashboard_result=dashboard_result or "NONE",
            dry_run=dry_run,
        )
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"ERROR {exc}")
        raise SystemExit(1)
