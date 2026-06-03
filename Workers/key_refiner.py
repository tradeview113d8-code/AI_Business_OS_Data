from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datetime import datetime
from Core.mongo import db
from Core.logger import log_event
from Core.health import heartbeat

WORKER = "key_refiner"

# Nhận diện provider từ prefix key
KEY_PATTERNS = {
    "openai":     "sk-",
    "openrouter": "sk-or-",
    "anthropic":  "sk-ant-",
    "gemini":     "AIza",
    "groq":       "gsk_",
    "cohere":     "co-",
}


def detect_provider(key_name: str, raw_key: str) -> str:
    name_lower = key_name.lower()
    for provider in KEY_PATTERNS:
        if provider in name_lower:
            return provider
    for provider, prefix in KEY_PATTERNS.items():
        if raw_key.startswith(prefix):
            return provider
    return "unknown"


def validate_key(raw_key: str) -> bool:
    return len(raw_key.strip()) >= 20


def run():
    heartbeat(WORKER)
    processed = 0
    failed    = 0

    raw_keys = list(db.api_keys_raw.find({"status": "raw"}))

    if not raw_keys:
        print("key_refiner: no raw keys to process")
        return

    for raw in raw_keys:
        try:
            key_name = raw.get("name", "")
            raw_key  = raw.get("key", "").strip()

            if not validate_key(raw_key):
                db.api_keys_raw.update_one(
                    {"_id": raw["_id"]},
                    {"$set": {"status": "invalid", "reason": "too_short"}}
                )
                failed += 1
                continue

            provider = detect_provider(key_name, raw_key)

            # Lưu vào api_keys (chuẩn)
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

            # Lưu vào api_key_vault (để Model Router dùng)
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

            # Đánh dấu raw đã xử lý
            db.api_keys_raw.update_one(
                {"_id": raw["_id"]},
                {"$set": {"status": "refined", "provider": provider}}
            )

            processed += 1
            log_event(WORKER, "INFO", f"refined: {key_name} → {provider}")
            print(f"[OK] {key_name} → {provider}")

        except Exception as e:
            failed += 1
            log_event(WORKER, "ERROR", f"failed {raw.get('name')}: {e}")
            print(f"[ERR] {raw.get('name')}: {e}")

    print(f"key_refiner done: processed={processed} failed={failed}")
    log_event(WORKER, "INFO", f"done processed={processed} failed={failed}")


if __name__ == "__main__":
    run()
            {"$set": {"status": "failed", "last_error": "health_check_failed"}}
        )
        publish(EventType.API_KEY_DEAD, WORKER, {
            "raw_key_id": str(raw_id),
            "name": name,
            "provider": provider
        })
        mark_processed(WORKER, str(raw_id))
        return

    # Khám phá models
    models = discover_models(provider, api_key)

    # Lưu vào api_keys_refined (KHÔNG lưu key)
    refined_doc = {
        "raw_key_id": str(raw_id),
        "name": name,
        "provider": provider,
        "status": "active",
        "supported_models": models,
        "refined_at": datetime.utcnow(),
        "health_score": health_score
    }
    db.api_keys_refined.update_one(
        {"raw_key_id": str(raw_id)},
        {"$set": refined_doc},
        upsert=True
    )

    db.api_keys_raw.update_one(
        {"_id": raw_id},
        {"$set": {"status": "processed"}}
    )

    publish(EventType.API_KEY_REFINED, WORKER, {
        "raw_key_id": str(raw_id),
        "provider": provider,
        "models": models
    })

    mark_processed(WORKER, str(raw_id))
    log_event(WORKER, "INFO", f"Refined key {name} -> {provider}")

def run():
    raw_keys = db.api_keys_raw.find({"status": "raw"})
    for key in raw_keys:
        refine_key(key)

if __name__ == "__main__":
    run()
