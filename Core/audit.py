from datetime import datetime
from Core.mongo import db

def audit(actor, action, target, metadata=None):
    db.audit_logs.insert_one({
        "actor":      str(actor),
        "action":     action,
        "target":     str(target),
        "metadata":   metadata or {},
        "timestamp":  datetime.utcnow()
    })
