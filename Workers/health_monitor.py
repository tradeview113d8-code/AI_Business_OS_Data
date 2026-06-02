from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datetime import datetime, timedelta
from Core.mongo import db
from Core.health import deep_health
from Core.logger import log_event

WORKER = "health_monitor"

def run():
    cutoff = datetime.utcnow() - timedelta(minutes=30)

    # Worker offline
    for w in db.health.find():
        if w.get("last_seen") and w["last_seen"] < cutoff:
            db.notifications.insert_one({
                "message":    f"Worker Offline: {w['worker']}",
                "sent":       False,
                "created_at": datetime.utcnow()
            })

    # Dead jobs hàng loạt
    dead_jobs = db.jobs.count_documents({"status": "dead"})
    if dead_jobs >= 5:
        db.notifications.insert_one({
            "message":    f"{dead_jobs} dead jobs — check system",
            "sent":       False,
            "created_at": datetime.utcnow()
        })

    # Dead events hàng loạt
    dead_events = db.events.count_documents({"status": "dead"})
    if dead_events >= 5:
        db.notifications.insert_one({
            "message":    f"{dead_events} dead events — check event bus",
            "sent":       False,
            "created_at": datetime.utcnow()
        })

    # Deep health
    status = deep_health()
    for service, state in status.items():
        if state == "down":
            db.notifications.insert_one({
                "message":    f"Service Down: {service}",
                "sent":       False,
                "created_at": datetime.utcnow()
            })

    log_event(WORKER, "INFO", "health scan completed")

if __name__ == "__main__":
    run()
