import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
MONGO_URI      = os.getenv("MONGO_URI", "")
GITHUB_TOKEN   = os.getenv("GITHUB_TOKEN", "")
GITHUB_OWNER   = os.getenv("GITHUB_OWNER", "")
GITHUB_REPO    = os.getenv("GITHUB_REPO", "")
MOCK_MODE      = os.getenv("MOCK_MODE", "false").lower() == "true"
DB_NAME        = os.getenv("DB_NAME", "business_os_v5")

ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
]
