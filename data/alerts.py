import os

import pandas as pd

from config.settings import ALERTS_FILE
from data.storage import load_csv_safe


def save_alert(row):
    columns = [
        "Time",
        "Ticker",
        "Price",
        "SMA20",
        "SMA50",
        "RSI",
        "Volume",
        "Avg_Volume_20",
        "Breakout_20",
        "Score",
        "Signal",
    ]

    alerts = load_csv_safe(ALERTS_FILE, columns)
    alerts = pd.concat([alerts, pd.DataFrame([row])], ignore_index=True)
    tmp_path = f"{ALERTS_FILE}.tmp"
    alerts.to_csv(tmp_path, index=False)
    os.replace(tmp_path, ALERTS_FILE)
