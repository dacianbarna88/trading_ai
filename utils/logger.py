from datetime import datetime
from config.settings import LOG_FILE


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"

    try:
        print(line)
    except OSError:
        pass

    # A logging failure (e.g. disk full) must never itself raise: log() is
    # the last line of defense inside the live bots' per-cycle crash
    # recovery handler, and an exception escaping from there would defeat
    # the whole point of that handler by crashing the process anyway.
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
