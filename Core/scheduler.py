import time
from datetime import datetime
from Core.mongo import db
from Core.job_queue import create_job
from Core.event_bus import publish
from Core.logger import log_event

WORKER = "scheduler"
POLL_INTERVAL = 10  # giây


def add_scheduled_task(task_type, run_at, payload=None, repeat_seconds=None):
    """
    Thêm task vào lịch.

    task_type      : tên job hoặc event_type
    run_at         : datetime UTC
    payload        : data kèm theo
    repeat_seconds : nếu set, task tự lặp lại sau N giây
    """
    return db.scheduled_tasks.insert_one({
        "task_type":      task_type,
        "run_at":         run_at,
        "payload":        payload or {},
        "status":         "pending",
        "repeat_seconds": repeat_seconds,
        "created_at":     datetime.utcnow()
    }).inserted_id


def _process_due_tasks():
    """Xử lý các task đến hạn."""
    now  = datetime.utcnow()
    fired = 0

    tasks = db.scheduled_tasks.find({
        "run_at": {"$lte": now},
        "status": "pending"
    })

    for task in tasks:
        try:
            # Tạo job hoặc publish event
            task_type = task["task_type"]
            payload   = task.get("payload", {})

            if task_type.startswith("job:"):
                create_job(task_type[4:], payload)
            else:
                publish(task_type, WORKER, payload)

            # Xử lý repeat
            repeat = task.get("repeat_seconds")
            if repeat:
                next_run = datetime.utcnow()
                next_run = next_run.replace(
                    second=next_run.second
                )
                from datetime import timedelta
                db.scheduled_tasks.update_one(
                    {"_id": task["_id"]},
                    {"$set": {
                        "status": "pending",
                        "run_at": datetime.utcnow() +
                                  timedelta(seconds=repeat)
                    }}
                )
            else:
                db.scheduled_tasks.update_one(
                    {"_id": task["_id"]},
                    {"$set": {"status": "completed"}}
                )

            fired += 1
            log_event(WORKER, "INFO", f"fired task: {task_type}")

        except Exception as e:
            db.scheduled_tasks.update_one(
                {"_id": task["_id"]},
                {"$set": {"status": "error", "last_error": str(e)}}
            )
            log_event(WORKER, "ERROR", f"task failed: {e}")

    return fired


def run_forever():
    """
    Scheduler daemon — chạy liên tục trên Oracle/VPS.
    Poll mỗi POLL_INTERVAL giây.
    """
    log_event(WORKER, "INFO",
              f"Scheduler started, poll every {POLL_INTERVAL}s")
    while True:
        try:
            fired = _process_due_tasks()
            if fired:
                log_event(WORKER, "INFO", f"fired {fired} tasks")
        except Exception as e:
            log_event(WORKER, "ERROR", f"scheduler error: {e}")
        time.sleep(POLL_INTERVAL)


def run_once():
    """Chạy 1 lần — dùng trong GitHub Actions."""
    return _process_due_tasks()
