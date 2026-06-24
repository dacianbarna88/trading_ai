import os
import shutil
from datetime import datetime

src = "."
backup_root = "backup_v41_safe"

timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M")
dest = os.path.join(backup_root, timestamp)

dest = os.path.abspath(dest)
src = os.path.abspath(src)

# 🔥 SAFETY CHECK (ANTI-LOOP)
if dest.startswith(src):
    raise Exception("BLOCKED: backup destination inside source tree")

os.makedirs(dest, exist_ok=True)

exclude = {
    "venv",
    "__pycache__",
    "backup_v41_safe"
}

for item in os.listdir(src):
    if item in exclude:
        continue

    s = os.path.join(src, item)
    d = os.path.join(dest, item)

    if os.path.isdir(s):
        shutil.copytree(s, d, dirs_exist_ok=True)
    else:
        shutil.copy2(s, d)

print("SAFE BACKUP DONE:", dest)
