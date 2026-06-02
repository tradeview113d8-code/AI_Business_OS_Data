from datetime import datetime
from Core.mongo import db, ping
from Core.config import GITHUB_TOKEN, TELEGRAM_TOKEN

def heartbeat(worker_name):
    try:
        db.health.update_one(
            {"worker": worker_name},
            {"$set": {"status": "healthy", "last_seen": datetime.utcnow()}},
            upsert=True
        )
    except:
        pass

def mongo_health():
    return "ok" if ping() else "down"

def github_health():
    try:
        if not GITHUB_TOKEN:
            return "not_configured"
        from github import Github
        Github(GITHUB_TOKEN).get_user().login
        return "ok"
    except:
        return "down"

def telegram_health():
    return "configured" if TELEGRAM_TOKEN else "not_configured"

def deep_health():
    status = {
        "mongo":      mongo_health(),
        "github":     github_health(),
        "telegram":   telegram_health(),
        "checked_at": datetime.utcnow()
    }
    try:
        db.system_health.insert_one(status)
    except:
        pass
    return status
