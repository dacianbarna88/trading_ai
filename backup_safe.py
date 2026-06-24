import os
import shutil
from datetime import datetime

src = "."
backup_root = "backup_v41_safe"

timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M")

dest = os.path.join(backup_root, timestamp)

os.makedirs(dest, exist_ok=True)

exclude = {"venv", "backup_v41_pre_market", "__pycache__"}

for item in os.listdir(src):
    if item in exclude:
        continue

    s = os.path.join(src, item)
    d = os.path.join(dest, item)

    if os.path.isdir(s):
        shutil.copytree(s, d, dirs_exist_ok=True)
    else:
        shutil.copy2(s, d)

print("BACKUP DONE:", dest)
