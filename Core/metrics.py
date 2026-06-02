from datetime import datetime
from Core.mongo import db

def save_metrics(worker, jobs_processed=0, failed=0, avg_time_ms=0):
    db.metrics.insert_one({
        "worker":         worker,
        "jobs_processed": jobs_processed,
        "failed":         failed,
        "avg_time_ms":    avg_time_ms,
        "timestamp":      datetime.utcnow()
    })
