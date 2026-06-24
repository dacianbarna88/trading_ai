import os
import signal
import subprocess
import sys

PID_FILE = "bot_pid.txt"
STATUS_FILE = "bot_status.txt"


def start_bot():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())

            os.kill(pid, 0)
            return "Botul pare deja pornit."
        except Exception:
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

    with open(PID_FILE, "w") as f:
        f.write(str(process.pid))

    with open(STATUS_FILE, "w") as f:
        f.write("RUNNING")

    return f"Bot pornit: {script}"


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