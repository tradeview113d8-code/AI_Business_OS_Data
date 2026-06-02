from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bson import ObjectId
from datetime import datetime
from Core.mongo import db
from Core.base_worker import BaseWorker
from Core.idempotency import already_processed, mark_processed
from Core.config import GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO, MOCK_MODE
from Core.circuit import CircuitBreaker
from Core.event_bus import publish, EventType

class ReportExporterWorker(BaseWorker):
    def __init__(self):
        super().__init__("report_exporter", "export_report")
        self.cb = CircuitBreaker(failure_threshold=3, recovery_timeout=120)

    def _upload(self, repo, path, content):
        def do():
            try:
                existing = repo.get_contents(path)
                repo.update_file(path, "update", content, existing.sha)
            except:
                repo.create_file(path, "create", content)
        self.cb.call(do)

    def process(self, job):
        report_id = job["payload"]["report_id"]
        if already_processed(self.name, report_id):
            return

        report = db.reports.find_one({"_id": ObjectId(report_id)})
        if not report:
            raise Exception(f"Report not found: {report_id}")

        if MOCK_MODE:
            print(f"[MOCK] Export report {report_id}")
        else:
            from github import Github
            repo = Github(GITHUB_TOKEN).get_repo(
                f"{GITHUB_OWNER}/{GITHUB_REPO}"
            )
            path = f"reports/{report['request_id']}/v{report['version']}.md"
            self._upload(repo, path, report["content"])

        db.notifications.insert_one({
            "message":    f"Report V{report['version']} exported",
            "sent":       False,
            "created_at": datetime.utcnow()
        })
        publish(EventType.REPORT_EXPORTED, self.name, {
            "report_id": report_id,
            "version":   report["version"]
        })
        mark_processed(self.name, report_id)

if __name__ == "__main__":
    ReportExporterWorker().run()
