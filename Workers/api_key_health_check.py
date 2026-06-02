# Workers/api_key_health_check.py
# ==================================================
# Định kỳ kiểm tra sức khỏe API Key đã refined
# ==================================================
from pathlib import Path
import sys
import requests
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from Core.mongo import db
from Core.event_bus import publish, EventType
from Core.logger import log_event
from Workers.key_refiner import check_key_health

WORKER = "api_health_check"

def run():
    cutoff = datetime.utcnow() - timedelta(hours=24)
    keys = db.api_keys_refined.find({
        "status": "active",
        "$or": [
            {"last_checked": {"$lt": cutoff}},
            {"last_checked": {"$exists": False}}
        ]
    })
    for refined in keys:
        raw_key = db.api_keys_raw.find_one({"_id": refined["raw_key_id"]})
        if not raw_key:
            continue
        api_key = raw_key.get("key", "")
        provider = refined["provider"]
        is_alive = check_key_health(provider, api_key)
        new_score = 100 if is_alive else 0
        if new_score != refined.get("health_score", 0):
            db.api_keys_refined.update_one(
                {"_id": refined["_id"]},
                {"$set": {"health_score": new_score, "last_checked": datetime.utcnow()}}
            )
            if new_score == 0:
                publish(EventType.API_KEY_DEAD, WORKER, {
                    "raw_key_id": refined["raw_key_id"],
                    "name": refined["name"],
                    "provider": provider
                })
                log_event(WORKER, "WARN", f"API key {refined['name']} died")

if __name__ == "__main__":
    run()
