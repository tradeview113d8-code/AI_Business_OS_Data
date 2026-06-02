import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db     = client[os.getenv("DB_NAME", "business_os_v5")]

collections = [
    # Core workflow
    "requests", "requests_refined",
    "jobs", "dead_letter_queue",
    "reports", "artifacts",
    # Event system
    "events", "dead_events",
    "notifications",
    # Knowledge
    "knowledge",
    # Operations
    "logs", "metrics", "audit_logs",
    "health", "system_health",
    "processing_logs",
    # Scheduler
    "scheduled_tasks",
    # Plugin system
    "plugin_registry",
    # Users & config
    "users", "config",
    "personal_knowledge",
    "api_keys_raw",
    "api_keys_refined",
    "api_channels",
]

created_count = 0
for c in collections:
    try:
        db.create_collection(c)
        created_count += 1
    except Exception as e:
        # Collection may already exist
        if "already exists" not in str(e):
            print(f"Warning creating {c}: {e}")

print(f"Bootstrap Complete — {len(collections)} collections ready ({created_count} newly created)")
