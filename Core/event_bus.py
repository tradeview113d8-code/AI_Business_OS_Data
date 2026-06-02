from datetime import datetime, timedelta
from pymongo import ReturnDocument
from Core.mongo import db

CLAIM_TIMEOUT_MINUTES = 30
MAX_RETRY             = 3


class EventType:
    # Core workflow
    REQUEST_RECEIVED   = "request_received"
    ANALYSIS_DONE      = "analysis_done"
    KNOWLEDGE_READY    = "knowledge_ready"
    REPORT_WRITTEN     = "report_written"
    REPORT_EXPORTED    = "report_exported"
    # System
    WORKER_OFFLINE     = "worker_offline"
    JOB_DEAD           = "job_dead"
    EVENT_DEAD         = "event_dead"
    SYSTEM_ALERT       = "system_alert"
    SCHEDULED_TRIGGER  = "scheduled_trigger"
    # Scheduled
    SCHEDULED_TRIGGER  = "scheduled_trigger"
    # OneAPI Integration
    API_KEY_RAW_ADDED  = "api_key_raw_added"
    API_KEY_REFINED    = "api_key_refined"
    API_KEY_DEAD       = "api_key_dead"
    CHANNEL_CREATED    = "channel_created"
    CHANNEL_UPDATED    = "channel_updated"
    CHANNEL_DISABLED   = "channel_disabled"


def publish(event_type, source, payload=None):
    """Phát Event lên Bus."""
    return db.events.insert_one({
        "event_type":  event_type,
        "source":      source,
        "payload":     payload or {},
        "status":      "pending",
        "claimed_by":  None,
        "claimed_at":  None,
        "retry_count": 0,
        "max_retry":   MAX_RETRY,
        "last_error":  None,
        "created_at":  datetime.utcnow()
    }).inserted_id


def recover_stuck_events():
    """Release event bị giữ quá CLAIM_TIMEOUT_MINUTES (worker crash)."""
    cutoff = datetime.utcnow() - timedelta(minutes=CLAIM_TIMEOUT_MINUTES)
    db.events.update_many(
        {"status": "processing", "claimed_at": {"$lt": cutoff}},
        {"$set": {
            "status":     "pending",
            "claimed_by": None,
            "claimed_at": None,
            "last_error": "claim_timeout_recovered"
        }}
    )


def consume(event_type, consumer_name):
    """
    Lấy 1 event pending — atomic, không race condition.
    Ghi claim để detect crash.
    """
    recover_stuck_events()
    return db.events.find_one_and_update(
        {
            "event_type": event_type,
            "status":     "pending"
        },
        {"$set": {
            "status":     "processing",
            "claimed_by": consumer_name,
            "claimed_at": datetime.utcnow()
        }},
        sort=[("created_at", 1)],
        return_document=ReturnDocument.AFTER
    )


def ack_event(event_id):
    """Xác nhận đã xử lý xong — chuyển sang completed."""
    from bson import ObjectId
    db.events.update_one(
        {"_id": ObjectId(str(event_id))},
        {"$set": {
            "status":      "completed",
            "claimed_by":  None,
            "finished_at": datetime.utcnow()
        }}
    )


def fail_event(event_id, error_msg=None):
    """Xử lý thất bại — retry hoặc chuyển sang dead_events."""
    from bson import ObjectId
    event = db.events.find_one({"_id": ObjectId(str(event_id))})
    if not event:
        return

    retries   = event.get("retry_count", 0) + 1
    max_retry = event.get("max_retry", MAX_RETRY)

    if retries >= max_retry:
        db.dead_events.insert_one({
            "original_event": event,
            "error":          str(error_msg),
            "failed_at":      datetime.utcnow()
        })
        db.events.update_one(
            {"_id": event["_id"]},
            {"$set": {
                "status":     "dead",
                "last_error": str(error_msg)
            }}
        )
        db.notifications.insert_one({
            "message":    f"Event Dead: {event.get('event_type')} — {str(error_msg)[:80]}",
            "sent":       False,
            "created_at": datetime.utcnow()
        })
        return

    backoff = min(3600, 2 ** retries)
    db.events.update_one(
        {"_id": event["_id"]},
        {
            "$inc": {"retry_count": 1},
            "$set": {
                "status":     "pending",
                "claimed_by": None,
                "claimed_at": None,
                "last_error": str(error_msg)
            }
        }
    )


def consume_all(event_type, consumer_name):
    """Lấy tất cả events pending — dùng cho batch."""
    events = []
    while True:
        event = consume(event_type, consumer_name)
        if not event:
            break
        events.append(event)
    return events


def pending_count(event_type):
    return db.events.count_documents({
        "event_type": event_type,
        "status":     "pending"
    })
