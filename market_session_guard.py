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

    from bot_controller import get_status, start_bot
    from markets.market_hours import any_market_open, get_market_statuses, get_open_markets

    dry_run = is_dry_run()
    statuses = get_market_statuses()
    open_markets = get_open_markets()
    closed_markets = [name for name, is_open in statuses.items() if not is_open]
    markets_open = any_market_open()
    bot_status = get_status()

    action = "NONE"
    result = ""
    awake_result = ""

    if markets_open:
        awake_result = ensure_awake_guard()

        if bot_status != "RUNNING":
            action = "START"
            if dry_run:
                result = "DRY_RUN would start bot"
            else:
                result = start_bot()
                bot_status = get_status()

    log(
        "OPEN=[{open}] CLOSED=[{closed}] BOT={bot} ACTION={action} "
        "AWAKE={awake} result={result} DRY_RUN={dry_run}".format(
            open=",".join(open_markets) if open_markets else "",
            closed=",".join(closed_markets) if closed_markets else "",
            bot=bot_status,
            action=action,
            awake=awake_result or "NONE",
            result=result or "NONE",
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
