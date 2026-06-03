from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datetime import datetime
from Core.mongo import db
from Core.logger import log_event
from Core.health import heartbeat

WORKER = "key_refiner"

KEY_PATTERNS = {
    "openai":     "sk-",
    "openrouter": "sk-or-",
    "anthropic":  "sk-ant-",
    "gemini":     "AIza",
    "groq":       "gsk_",
    "cohere":     "co-",
}


def detect_provider(key_name, raw_key):
    name_lower = key_name.lower()
    for provider in KEY_PATTERNS:
        if provider in name_lower:
            return provider
    for provider, prefix in KEY_PATTERNS.items():
        if raw_key.startswith(prefix):
            return provider
    return "unknown"


def validate_key(raw_key):
    return len(raw_key.strip()) >= 20


def run():
    heartbeat(WORKER)
    processed = 0
    failed = 0

    raw_keys = list(db.api_keys_raw.find({"status": "raw"}))

    if not raw_keys:
        print("key_refiner: no raw keys to process")
        return

    for raw in raw_keys:
        try:
            key_name = raw.get("name", "")
            raw_key = raw.get("key", "").strip()

            if not validate_key(raw_key):
                db.api_keys_raw.update_one(
                    {"_id": raw["_id"]},
                    {"$set": {"status": "invalid", "reason": "too_short"}}
                )
                failed += 1
                continue

            provider = detect_provider(key_name, raw_key)

            db.api_keys.update_one(
                {"name": key_name},
                {"$set": {
                    "name":        key_name,
                    "key":         raw_key,
                    "provider":    provider,
                    "status":      "active",
                    "usage_count": 0,
                    "created_by":  raw.get("created_by"),
                    "created_at":  raw.get("created_at", datetime.utcnow()),
                    "updated_at":  datetime.utcnow()
                }},
                upsert=True
            )

            db.api_key_vault.update_one(
                {"provider": provider, "key": raw_key},
                {"$set": {
                    "provider":    provider,
                    "key":         raw_key,
                    "name":        key_name,
                    "status":      "active",
                    "usage_count": 0,
                    "error_count": 0,
                    "last_used":   None,
                    "added_at":    datetime.utcnow()
                }},
                upsert=True
            )

            db.api_keys_raw.update_one(
                {"_id": raw["_id"]},
                {"$set": {"status": "refined", "provider": provider}}
            )

            processed += 1
            log_event(WORKER, "INFO", f"refined: {key_name} provider={provider}")
            print(f"[OK] {key_name} -> {provider}")

        except Exception as e:
            failed += 1
            log_event(WORKER, "ERROR", f"failed {raw.get('name')}: {e}")
            print(f"[ERR] {raw.get('name')}: {e}")

    print(f"key_refiner done: processed={processed} failed={failed}")
    log_event(WORKER, "INFO", f"done processed={processed} failed={failed}")


if __name__ == "__main__":
    run()
