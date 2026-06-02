import os

REQUIRED = ["MONGO_URI", "TELEGRAM_TOKEN", "ADMIN_IDS", "DB_NAME"]

def validate_env():
    missing = [v for v in REQUIRED if not os.getenv(v)]
    if missing:
        raise Exception(f"Missing env vars: {', '.join(missing)}")
