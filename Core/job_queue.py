from datetime import datetime, timedelta
from pymongo import ReturnDocument
from Core.mongo import db

MAX_RETRY     = 3
STUCK_MINUTES = 30

def create_job(job_type, payload, created_by=None, priority=5):
    return db.jobs.insert_one({
        "type":          job_type,
        "status":        "pending",
        "priority":      priority,
        "retry_count":   0,
        "max_retry":     MAX_RETRY,
        "created_by":    created_by,
        "claimed_by":    None,
        "payload":       payload,
        "last_error":    None,
        "next_retry_at": datetime.utcnow(),
        "created_at":    datetime.utcnow(),
        "started_at":    None,
        "finished_at":   None
    })

def recover_stuck_jobs():
    cutoff = datetime.utcnow() - timedelta(minutes=STUCK_MINUTES)
    db.jobs.update_many(
        {"status": "processing", "started_at": {"$lt": cutoff}},
        {"$set": {
            "status":     "pending",
            "claimed_by": None,
            "last_error": "stuck_recovered"
        }}
    )

def claim_job(job_type, worker_name):
    recover_stuck_jobs()
    return db.jobs.find_one_and_update(
        {
            "type":          job_type,
            "status":        "pending",
            "next_retry_at": {"$lte": datetime.utcnow()}
        },
        {"$set": {
            "status":     "processing",
            "claimed_by": worker_name,
            "started_at": datetime.utcnow()
        }},
        sort=[("priority", 1), ("created_at", 1)],
        return_document=ReturnDocument.AFTER
    )

def complete_job(job_id):
    db.jobs.update_one(
        {"_id": job_id},
        {"$set": {"status": "completed", "finished_at": datetime.utcnow()}}
    )

def fail_job(job_id, error_msg=None):
    job = db.jobs.find_one({"_id": job_id})
    if not job:
        return
    retries   = job.get("retry_count", 0) + 1
    max_retry = job.get("max_retry", MAX_RETRY)

    if retries >= max_retry:
        db.dead_letter_queue.insert_one({
            "job_id":           job_id,
            "job_type":         job.get("type"),
            "original_payload": job.get("payload"),
            "error":            str(error_msg),
            "retry_count":      retries,
            "failed_at":        datetime.utcnow()
        })
        db.jobs.update_one(
            {"_id": job_id},
            {"$set": {
                "status":      "dead",
                "last_error":  str(error_msg),
                "finished_at": datetime.utcnow()
            }}
        )
        db.notifications.insert_one({
            "message":    f"Job Dead: {job_id} ({job.get('type')})",
            "sent":       False,
            "created_at": datetime.utcnow()
        })
        return

    backoff = min(3600, 30 * (2 ** retries))
    db.jobs.update_one(
        {"_id": job_id},
        {
            "$inc": {"retry_count": 1},
            "$set": {
                "status":        "pending",
                "claimed_by":    None,
                "last_error":    str(error_msg),
                "next_retry_at": datetime.utcnow() + timedelta(seconds=backoff)
            }
        }
    )

def reset_job(job_id, actor="system"):
    from Core.audit import audit
    db.jobs.update_one(
        {"_id": job_id},
        {"$set": {
            "status":        "pending",
            "retry_count":   0,
            "claimed_by":    None,
            "last_error":    None,
            "started_at":    None,
            "finished_at":   None,
            "next_retry_at": datetime.utcnow()
        }}
    )
    audit(actor, "reset_job", job_id)

def queue_stats():
    return {
        "pending":    db.jobs.count_documents({"status": "pending"}),
        "processing": db.jobs.count_documents({"status": "processing"}),
        "completed":  db.jobs.count_documents({"status": "completed"}),
        "dead":       db.jobs.count_documents({"status": "dead"})
    }
