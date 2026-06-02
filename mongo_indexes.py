import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME", "business_os_v5")]

print("Đang thiết lập Index...")

# --- Enhanced Index Dropping Logic for 'events' ---
if 'events' in db.list_collection_names():
    for idx in db.events.list_indexes():
        # Drop all indexes on 'events' except the default '_id_' index
        if idx['name'] != '_id_':
            try:
                print(f"-> Xóa index cũ trên 'events': {idx['name']}")
                db.events.drop_index(idx['name'])
            except Exception as e:
                print(f"Error dropping index {idx['name']}: {e}")

# Jobs indexes
try:
    db.jobs.create_index("status")
    db.jobs.create_index("type")
    db.jobs.create_index("priority")
    print("✓ Created jobs indexes")
except Exception as e:
    print(f"✗ Error creating jobs indexes: {e}")

# Events indexes (TTL 30 days)
try:
    db.events.create_index(
        [("created_at", 1)],
        name="events_ttl",
        expireAfterSeconds=2592000
    )
    db.events.create_index("event_type")
    print("✓ Created events indexes")
except Exception as e:
    print(f"✗ Error creating events indexes: {e}")

# OneAPI collections
try:
    db.api_keys_raw.create_index("status")
    db.api_keys_raw.create_index("created_at")
    db.api_keys_raw.create_index("source")
    print("✓ Created api_keys_raw indexes")
except Exception as e:
    print(f"✗ Error creating api_keys_raw indexes: {e}")

try:
    db.api_keys_refined.create_index("raw_key_id", unique=True)
    db.api_keys_refined.create_index("provider")
    db.api_keys_refined.create_index("status")
    print("✓ Created api_keys_refined indexes")
except Exception as e:
    print(f"✗ Error creating api_keys_refined indexes: {e}")

try:
    db.api_channels.create_index([("raw_key_id", 1), ("model", 1)], unique=True)
    db.api_channels.create_index("enabled")
    db.api_channels.create_index("provider")
    print("✓ Created api_channels indexes")
except Exception as e:
    print(f"✗ Error creating api_channels indexes: {e}")

print("\nIndex setup complete.")
