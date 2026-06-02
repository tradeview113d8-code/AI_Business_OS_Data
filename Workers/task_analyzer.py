from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bson import ObjectId
from datetime import datetime
from Core.mongo import db
from Core.base_worker import BaseWorker
from Core.idempotency import already_processed, mark_processed
from Core.job_queue import create_job
from Core.event_bus import publish, EventType

class TaskAnalyzerWorker(BaseWorker):
    def __init__(self):
        super().__init__("task_analyzer", "analyze_request")

    def process(self, job):
        request_id = job["payload"]["request_id"]
        if already_processed(self.name, request_id):
            return

        request = db.requests.find_one({"_id": ObjectId(request_id)})
        if not request:
            raise Exception(f"Request not found: {request_id}")

        refined_id = db.requests_refined.insert_one({
            "request_id": request_id,
            "prompt":     request.get("prompt"),
            "intent":     "pending_analysis",
            "priority":   5,
            "created_at": datetime.utcnow()
        }).inserted_id

        db.requests.update_one(
            {"_id": request["_id"]},
            {"$set": {"status": "analyzed"}}
        )

        create_job("write_report", {"refined_id": str(refined_id)})
        publish(EventType.ANALYSIS_DONE, self.name, {
            "request_id": request_id,
            "refined_id": str(refined_id)
        })
        mark_processed(self.name, request_id)

if __name__ == "__main__":
    TaskAnalyzerWorker().run()
