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

    script = "live_bot.py" if os.path.exists("live_bot.py") else "telegram_bot.py"

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