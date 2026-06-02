from datetime import datetime
from Core.mongo import db

def log_event(worker, level, message, metadata=None):
    try:
        db.logs.insert_one({
            "worker":     worker,
            "level":      level,
            "message":    str(message),
            "metadata":   metadata or {},
            "created_at": datetime.utcnow()
        })
    except:
        pass
