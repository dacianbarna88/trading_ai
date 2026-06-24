from pathlib import Path
from config.settings import STATUS_FILE


def set_status(status):
    Path(STATUS_FILE).write_text(status, encoding="utf-8")
