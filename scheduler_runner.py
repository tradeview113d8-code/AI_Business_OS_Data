"""
Scheduler Runner — chạy liên tục trên Oracle/VPS.

python scheduler_runner.py
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from Core.scheduler import run_forever, run_once, add_scheduled_task

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "forever"
    if mode == "once":
        fired = run_once()
        print(f"Fired {fired} tasks")
    else:
        run_forever()
