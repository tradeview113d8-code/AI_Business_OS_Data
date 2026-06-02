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

for c in collections:
    db[c]

print(f"Bootstrap Complete — {len(collections)} collections ready")
