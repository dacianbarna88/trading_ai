import os
import signal
import socket
import subprocess
import sys
from datetime import datetime

PID_FILE = "bot_pid.txt"
STATUS_FILE = "bot_status.txt"
DASHBOARD_PID_FILE = "dashboard_pid.txt"
DASHBOARD_STATUS_FILE = "dashboard_status.txt"
DASHBOARD_PORT = 8501
STARTUP_LOG = "startup_ops.log"
BOT_SCRIPT = "live_bot.py"
FALLBACK_SCRIPT = "telegram_bot.py"


def _log_startup(message):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    with open(STARTUP_LOG, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(line)


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _read_pid(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return int(handle.read().strip())
    except Exception:
        return None


def _port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _pgrep_pids(pattern: str) -> list[int]:
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return []
    if result.returncode != 0:
        return []
    pids: list[int] = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def get_bot_script() -> str:
    return BOT_SCRIPT if os.path.exists(BOT_SCRIPT) else FALLBACK_SCRIPT


def get_bot_start_command() -> str:
    return f"{sys.executable} {get_bot_script()}"


def start_bot_verified() -> dict:
    """Start bot and return structured verification details for session guard logs."""
    script = get_bot_script()
    command = get_bot_start_command()
    message = start_bot()
    pid = _read_pid(PID_FILE)
    pid_alive = bool(pid and _pid_alive(pid))
    pgrep_pids = _pgrep_pids(script)
    failure_reason = None
    if "deja" not in message.lower() and pid is not None and not pid_alive:
        failure_reason = "pid_not_alive_after_start"
    elif pid is None and "deja" not in message.lower():
        failure_reason = "pid_file_not_written"
    _log_startup(
        "START_BOT_VERIFY "
        f"command={command} pid={pid} pid_alive={pid_alive} pgrep={pgrep_pids} "
        f"failure={failure_reason or 'NONE'}"
    )
    return {
        "message": message,
        "pid": pid,
        "pid_alive": pid_alive,
        "pgrep_pids": pgrep_pids,
        "command": command,
        "failure_reason": failure_reason,
    }


def start_dashboard_verified() -> dict:
    message = start_dashboard()
    pid = _read_pid(DASHBOARD_PID_FILE)
    pid_alive = bool(pid and _pid_alive(pid))
    port_open = _port_in_use(DASHBOARD_PORT)
    pgrep_pids = _pgrep_pids("streamlit run dashboard_v2.py")
    failure_reason = None
    if not port_open and not pid_alive:
        failure_reason = "dashboard_not_listening"
    _log_startup(
        "START_DASHBOARD_VERIFY "
        f"port={DASHBOARD_PORT} port_open={port_open} pid={pid} "
        f"pid_alive={pid_alive} pgrep={pgrep_pids} failure={failure_reason or 'NONE'}"
    )
    return {
        "message": message,
        "pid": pid,
        "pid_alive": pid_alive or port_open,
        "pgrep_pids": pgrep_pids,
        "command": f"{sys.executable} -m streamlit run dashboard_v2.py --server.port {DASHBOARD_PORT}",
        "failure_reason": failure_reason,
    }


def start_bot():
    existing = _read_pid(PID_FILE)
    if existing and _pid_alive(existing):
        _log_startup(f"START_BOT skipped reason=already_running pid={existing}")
        return "Botul pare deja pornit."

    if existing:
        try:
            os.remove(PID_FILE)
        except Exception:
            pass

    script = get_bot_script()

    process = subprocess.Popen(
        [sys.executable, script],
        stdout=open("bot_output.log", "a"),
        stderr=open("bot_error.log", "a"),
    )

    with open(PID_FILE, "w", encoding="utf-8") as handle:
        handle.write(str(process.pid))

    with open(STATUS_FILE, "w", encoding="utf-8") as handle:
        handle.write("RUNNING")

    _log_startup(f"START_BOT reason=controller_invoke script={script} pid={process.pid}")
    return f"Bot pornit: {script}"


def start_dashboard():
    if _port_in_use(DASHBOARD_PORT):
        with open(DASHBOARD_STATUS_FILE, "w", encoding="utf-8") as handle:
            handle.write("RUNNING")
        _log_startup(f"START_DASHBOARD skipped reason=port_in_use port={DASHBOARD_PORT}")
        return f"Dashboard deja activ pe port {DASHBOARD_PORT}."

    existing = _read_pid(DASHBOARD_PID_FILE)
    if existing and _pid_alive(existing):
        with open(DASHBOARD_STATUS_FILE, "w", encoding="utf-8") as handle:
            handle.write("RUNNING")
        _log_startup(f"START_DASHBOARD skipped reason=already_running pid={existing}")
        return "Dashboard pare deja pornit."

    if existing:
        try:
            os.remove(DASHBOARD_PID_FILE)
        except Exception:
            pass

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "dashboard_v2.py",
            "--server.port",
            str(DASHBOARD_PORT),
            "--server.headless",
            "true",
        ],
        stdout=open("dashboard_output.log", "a"),
        stderr=open("dashboard_error.log", "a"),
    )

    with open(DASHBOARD_PID_FILE, "w", encoding="utf-8") as handle:
        handle.write(str(process.pid))

    with open(DASHBOARD_STATUS_FILE, "w", encoding="utf-8") as handle:
        handle.write("RUNNING")

    _log_startup(
        f"START_DASHBOARD reason=controller_invoke port={DASHBOARD_PORT} pid={process.pid}"
    )
    return f"Dashboard pornit pe port {DASHBOARD_PORT}."


def stop_bot():
    if not os.path.exists(PID_FILE):
        with open(STATUS_FILE, "w") as f:
            f.write("STOPPED")
        return "Botul nu era pornit."

    with open(PID_FILE, "r") as f:
        pid = int(f.read().strip())

    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        pass

    try:
        os.remove(PID_FILE)
    except Exception:
        pass

    with open(STATUS_FILE, "w") as f:
        f.write("STOPPED")

    return "Bot oprit cu succes."


def get_status():
    if not os.path.exists(PID_FILE):
        return "STOPPED"

    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())

        os.kill(pid, 0)

        with open(STATUS_FILE, "w") as f:
            f.write("RUNNING")

        return "RUNNING"

    except Exception:
        try:
            os.remove(PID_FILE)
        except Exception:
            pass

        with open(STATUS_FILE, "w") as f:
            f.write("STOPPED")

        return "STOPPED"


def get_dashboard_status():
    if _port_in_use(DASHBOARD_PORT):
        with open(DASHBOARD_STATUS_FILE, "w", encoding="utf-8") as handle:
            handle.write("RUNNING")
        return "RUNNING"

    pid = _read_pid(DASHBOARD_PID_FILE)
    if pid and _pid_alive(pid):
        with open(DASHBOARD_STATUS_FILE, "w", encoding="utf-8") as handle:
            handle.write("RUNNING")
        return "RUNNING"

    try:
        if os.path.exists(DASHBOARD_PID_FILE):
            os.remove(DASHBOARD_PID_FILE)
    except Exception:
        pass

    with open(DASHBOARD_STATUS_FILE, "w", encoding="utf-8") as handle:
        handle.write("STOPPED")

    return "STOPPED"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TAE bot/dashboard controller")
    parser.add_argument(
        "action",
        choices=["start", "start-bot", "start-dashboard", "stop", "status"],
        help="Controller action",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Start even when market sessions are closed (manual operator override)",
    )
    cli = parser.parse_args()

    def _market_closed() -> bool:
        try:
            from markets.market_hours import any_market_open

            return not any_market_open()
        except ImportError:
            return False

    if cli.action in {"start", "start-bot"}:
        if not cli.force and _market_closed():
            print(
                "Refused: all market sessions closed. "
                "Use --force for manual operator override."
            )
            raise SystemExit(2)
        detail = start_bot_verified()
        print(detail["message"])
        print(f"PID={detail['pid']} alive={detail['pid_alive']} pgrep={detail['pgrep_pids']}")
        if cli.action == "start-bot":
            raise SystemExit(0 if detail["pid_alive"] else 1)

    if cli.action in {"start", "start-dashboard"}:
        detail = start_dashboard_verified()
        print(detail["message"])
        print(f"PID={detail['pid']} alive={detail['pid_alive']} pgrep={detail['pgrep_pids']}")
        if cli.action == "start-dashboard":
            raise SystemExit(0 if detail["pid_alive"] else 1)

    if cli.action == "start":
        raise SystemExit(0)

    if cli.action == "stop":
        print(stop_bot())
        raise SystemExit(0)

    if cli.action == "status":
        print(f"bot={get_status()} dashboard={get_dashboard_status()}")
        raise SystemExit(0)