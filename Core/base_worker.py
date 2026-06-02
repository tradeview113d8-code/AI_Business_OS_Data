import time
import traceback
from Core.health import heartbeat
from Core.logger import log_event
from Core.metrics import save_metrics
from Core.job_queue import claim_job, complete_job, fail_job

class BaseWorker:
    """
    Kế thừa class này cho mọi job worker.

    class MyWorker(BaseWorker):
        def __init__(self):
            super().__init__("my_worker", "my_job_type")
        def process(self, job):
            # logic ở đây
    """
    def __init__(self, name, job_type):
        self.name      = name
        self.job_type  = job_type
        self.processed = 0
        self.failed    = 0
        self.total_ms  = 0

    def process(self, job):
        raise NotImplementedError

    def before_run(self): pass
    def after_run(self):  pass

    def run(self):
        heartbeat(self.name)
        self.before_run()
        while True:
            job = claim_job(self.job_type, self.name)
            if not job:
                break
            start = time.time()
            try:
                self.process(job)
                complete_job(job["_id"])
                self.processed += 1
                log_event(self.name, "INFO",
                          f"completed job {job['_id']}")
            except Exception as e:
                self.failed += 1
                fail_job(job["_id"], traceback.format_exc())
                log_event(self.name, "ERROR",
                          f"failed job {job['_id']}: {e}")
            self.total_ms += (time.time() - start) * 1000

        avg_ms = int(self.total_ms / self.processed) if self.processed else 0
        save_metrics(self.name, self.processed, self.failed, avg_ms)
        self.after_run()
