from pathlib import Path
from datetime import datetime
import shutil

BACKUP_DIR = Path("backups")

CLOUD_DIR = Path(
    "/Users/book/Library/Mobile Documents/com~apple~CloudDocs/TradingAI_Backups"
)

REPORT = "cloud_backup_sync_report.txt"

CLOUD_DIR.mkdir(parents=True, exist_ok=True)

if not BACKUP_DIR.exists():
    print("backups folder missing")
    raise SystemExit

backups = sorted(
    BACKUP_DIR.glob("TradingAI_Backup_*.zip"),
    key=lambda p: p.stat().st_mtime,
    reverse=True
)

if not backups:
    print("No backup zip files found")
    raise SystemExit

latest = backups[0]

destination = CLOUD_DIR / latest.name

shutil.copy2(
    latest,
    destination
)

size_mb = round(
    destination.stat().st_size / 1024 / 1024,
    2
)

report = f"""
===== V32.6.1 ICLOUD BACKUP SYNC =====

Timestamp:
{datetime.now()}

Source:
{latest}

Destination:
{destination}

Size:
{size_mb} MB

Status:
SUCCESS

Cloud:
iCloud Drive

Mode:
BACKUP_ONLY
NO_TRADING_CHANGE
NO_BROKER
"""

Path(REPORT).write_text(report)

print(report)
