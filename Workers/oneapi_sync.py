# Workers/oneapi_sync.py
# ==================================================
# Đồng bộ api_keys_refined -> api_channels
# ==================================================
from pathlib import Path
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from Core.mongo import db
from Core.event_bus import publish, EventType
from Core.logger import log_event
from Core.idempotency import already_processed, mark_processed

WORKER = "oneapi_sync"

def sync_channels():
    refined_keys = db.api_keys_refined.find({"status": "active"})
    for refined in refined_keys:
        key_id = refined["_id"]
        if already_processed(WORKER, str(key_id)):
            continue

        raw_key_id = refined["raw_key_id"]
        provider = refined["provider"]
        models = refined.get("supported_models", [])

        for model in models:
            channel_doc = {
                "raw_key_id": raw_key_id,
                "provider": provider,
                "model": model,
                "enabled": True,
                "weight": 1,
                "last_sync_at": datetime.utcnow()
            }
            result = db.api_channels.update_one(
                {"raw_key_id": raw_key_id, "model": model},
                {"$set": channel_doc},
                upsert=True
            )
            if result.upserted_id:
                publish(EventType.CHANNEL_CREATED, WORKER, {
                    "channel_id": str(result.upserted_id),
                    "provider": provider,
                    "model": model
                })
                log_event(WORKER, "INFO", f"Created channel {provider}/{model}")

        mark_processed(WORKER, str(key_id))

    # Vô hiệu hóa channel cũ không còn active
    active_raw_ids = [r["raw_key_id"] for r in refined_keys]
    db.api_channels.update_many(
        {"raw_key_id": {"$nin": active_raw_ids}, "enabled": True},
        {"$set": {"enabled": False, "disabled_at": datetime.utcnow()}}
    )

def run():
    sync_channels()

if __name__ == "__main__":
    run()
