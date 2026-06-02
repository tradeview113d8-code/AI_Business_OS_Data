from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datetime import datetime, timedelta
from Core.mongo import db
from Core.logger import log_event

WORKER = "cleaner"

def run():
    cutoff_7d  = datetime.utcnow() - timedelta(days=7)
    cutoff_30d = datetime.utcnow() - timedelta(days=30)

    r1 = db.jobs.delete_many({
        "status": "completed", "finished_at": {"$lt": cutoff_7d}
    })
    r2 = db.logs.delete_many({"created_at": {"$lt": cutoff_7d}})
    r3 = db.notifications.delete_many({
        "sent": True, "created_at": {"$lt": cutoff_7d}
    })
    r4 = db.system_health.delete_many({"checked_at": {"$lt": cutoff_7d}})
    r5 = db.events.delete_many({
        "status": "completed", "created_at": {"$lt": cutoff_30d}
    })
    r6 = db.metrics.delete_many({"timestamp": {"$lt": cutoff_30d}})

    log_event(WORKER, "INFO",
        f"cleaned jobs={r1.deleted_count} logs={r2.deleted_count} "
        f"notifs={r3.deleted_count} health={r4.deleted_count} "
        f"events={r5.deleted_count} metrics={r6.deleted_count}"
    )

if __name__ == "__main__":
    run()
