from datetime import datetime
from Core.mongo import db

def already_processed(worker, entity_id):
    key = f"{worker}:{entity_id}"
    return db.processing_logs.find_one(
        {"key": key, "status": "done"}
    ) is not None

def mark_processed(worker, entity_id, metadata=None):
    key = f"{worker}:{entity_id}"
    db.processing_logs.update_one(
        {"key": key},
        {"$set": {
            "worker":       worker,
            "entity_id":    str(entity_id),
            "status":       "done",
            "metadata":     metadata or {},
            "processed_at": datetime.utcnow()
        }},
        upsert=True
    )
