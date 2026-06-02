import shutil
from pathlib import Path

ROOT   = Path("/content/AI_Business_OS_V5")
OUTPUT = "/content/AI_Business_OS_V5"

shutil.make_archive(OUTPUT, "zip", ROOT)
print(f"ZIP: {OUTPUT}.zip")
