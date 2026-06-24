from pathlib import Path
from datetime import datetime
import zipfile

timestamp = datetime.now().strftime(
    "%Y_%m_%d_%H_%M_%S"
)

backup_dir = Path("backups")
backup_dir.mkdir(exist_ok=True)

zip_name = (
    backup_dir /
    f"TradingAI_Backup_{timestamp}.zip"
)

excluded = {
    "venv",
    "__pycache__",
    "backups",
}

file_count = 0

with zipfile.ZipFile(
    zip_name,
    "w",
    zipfile.ZIP_DEFLATED
) as z:

    for path in Path(".").rglob("*"):

        skip = False

        for part in path.parts:
            if part in excluded:
                skip = True
                break

        if skip:
            continue

        if path.is_file():

            z.write(
                path,
                path
            )

            file_count += 1

size_mb = round(
    zip_name.stat().st_size /
    1024 /
    1024,
    2
)

report = f"""
===== V32.5 BACKUP ENGINE =====

Backup File:
{zip_name}

Files Archived:
{file_count}

Archive Size:
{size_mb} MB

Excluded:
venv
__pycache__
backups

Status:
SUCCESS
"""

Path(
    "backup_engine_report.txt"
).write_text(report)

print(report)
