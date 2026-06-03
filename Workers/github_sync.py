from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import json
import signal
from datetime import datetime
from Core.mongo import db
from Core.config import GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO, MOCK_MODE
from Core.logger import log_event
from Core.circuit import CircuitBreaker

WORKER   = "github_sync"
cb       = CircuitBreaker(failure_threshold=3, recovery_timeout=120)
MAX_DOCS = 20  # Giới hạn số doc/collection — tránh timeout


def timeout_handler(signum, frame):
    raise TimeoutError("github_sync exceeded time limit")


def to_markdown(collection, doc):
    doc_id  = str(doc.get("_id", ""))
    updated = str(doc.get("updated_at", doc.get("created_at", "")))
    body    = {k: str(v) for k, v in doc.items() if k != "_id"}
    return (
        f"# {collection} / {doc_id}\n\n"
        f"Updated: {updated}\n\n"
        f"```json\n{json.dumps(body, indent=2, ensure_ascii=False)}\n```\n"
    )


def sync_file(repo, path, content):
    def do():
        try:
            existing = repo.get_contents(path)
            repo.update_file(path, "sync", content, existing.sha)
        except Exception:
            repo.create_file(path, "sync", content)
    cb.call(do)


def run():
    # Hard timeout 80 giây (Linux only)
    try:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(80)
    except (AttributeError, OSError):
        pass

    collections = ["personal_knowledge", "config"]
    synced = 0

    if MOCK_MODE:
        for col in collections:
            print(f"[MOCK] Would sync {db[col].count_documents({})} docs from {col}")
        return

    try:
        from github import Github
        repo = Github(GITHUB_TOKEN).get_repo(f"{GITHUB_OWNER}/{GITHUB_REPO}")
    except Exception as e:
        log_event(WORKER, "ERROR", f"GitHub connect failed: {e}")
        print(f"GitHub connect failed: {e}")
        return

    for col in collections:
        docs = list(db[col].find().sort("created_at", -1).limit(MAX_DOCS))
        for doc in docs:
            try:
                path    = f"sync_logs/{col}/{doc['_id']}.md"
                content = to_markdown(col, doc)
                sync_file(repo, path, content)
                synced += 1
            except Exception as e:
                log_event(WORKER, "ERROR", f"sync failed {doc['_id']}: {e}")
                if cb.state == "open":
                    log_event(WORKER, "WARN", "Circuit open — aborting sync")
                    print("Circuit open — aborting github_sync")
                    break

    try:
        signal.alarm(0)
    except (AttributeError, OSError):
        pass

    log_event(WORKER, "INFO", f"synced {synced} docs")
    print(f"GitHub sync complete: {synced} docs")


if __name__ == "__main__":
    run()
