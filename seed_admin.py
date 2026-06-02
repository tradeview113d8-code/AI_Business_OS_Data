import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db     = client[os.getenv("DB_NAME", "business_os_v5")]

admin_ids = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
]
for admin_id in admin_ids:
    db.users.update_one(
        {"telegram_id": admin_id},
        {"$set": {"role": "admin"}},
        upsert=True
    )
    print(f"Seeded admin: {admin_id}")

print("Seed Complete")
