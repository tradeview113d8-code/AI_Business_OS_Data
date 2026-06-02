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
from Core.knowledge import save_knowledge, KnowledgeType

class ReportWriterWorker(BaseWorker):
    def __init__(self):
        super().__init__("report_writer", "write_report")

    def process(self, job):
        refined_id = job["payload"]["refined_id"]
        if already_processed(self.name, refined_id):
            return

        refined = db.requests_refined.find_one({"_id": ObjectId(refined_id)})
        if not refined:
            raise Exception(f"Refined not found: {refined_id}")

        latest  = db.reports.find_one(
            {"request_id": refined["request_id"]},
            sort=[("version", -1)]
        )
        version = 1 if not latest else latest["version"] + 1

        content = f"""# AI BUSINESS REPORT V{version}
Generated: {datetime.utcnow()}
Request ID: {refined["request_id"]}

## Original Prompt
{refined.get("prompt", "")}

## Analysis
Intent:   {refined.get("intent", "pending")}
Priority: {refined.get("priority", 5)}

## Next Steps
- Connect LLM to generate real content
"""
        report_id = db.reports.insert_one({
            "request_id": refined["request_id"],
            "version":    version,
            "content":    content,
            "created_at": datetime.utcnow()
        }).inserted_id

        # Lưu vào Knowledge Bus
        save_knowledge(
            source         = self.name,
            knowledge_type = KnowledgeType.IMPLEMENTATION_PLAN,
            content        = content,
            request_id     = refined["request_id"],
            tags           = ["report", f"v{version}"]
        )

        create_job("export_report", {"report_id": str(report_id)})
        publish(EventType.REPORT_WRITTEN, self.name, {
            "report_id":  str(report_id),
            "request_id": refined["request_id"],
            "version":    version
        })
        mark_processed(self.name, refined_id)

if __name__ == "__main__":
    ReportWriterWorker().run()
