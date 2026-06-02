# Workers/key_refiner.py
# ==================================================
# Phát hiện provider, tự kiểm tra, khám phá models
# ==================================================
from pathlib import Path
import sys
import requests
import re
from datetime import datetime
from bson import ObjectId

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from Core.mongo import db
from Core.event_bus import publish, EventType
from Core.logger import log_event
from Core.idempotency import already_processed, mark_processed

WORKER = "key_refiner"

# Mapping provider dựa trên prefix hoặc pattern
PROVIDER_PATTERNS = [
    (re.compile(r"^AIza[0-9A-Za-z\-_]+$"), "google", "gemini"),
    (re.compile(r"^gsk_[A-Za-z0-9]+$"), "groq", "groq"),
    (re.compile(r"^sk-[A-Za-z0-9]+$"), "openai", "openai"),
    (re.compile(r"^sk-or-v1-[A-Za-z0-9]+$"), "openrouter", "openrouter"),
    (re.compile(r"^[A-Za-z0-9]{32,}$"), "generic", "unknown")
]

# Model discovery endpoints (nếu có)
MODEL_ENDPOINTS = {
    "openai": "https://api.openai.com/v1/models",
    "groq": "https://api.groq.com/openai/v1/models",
    "openrouter": "https://openrouter.ai/api/v1/models"
}

# Fallback models
FALLBACK_MODELS = {
    "google": ["gemini-2.5-flash", "gemini-2.5-pro"],
    "groq": ["llama3-70b-8192", "mixtral-8x7b-32768"],
    "openai": ["gpt-4o", "gpt-4-turbo"],
    "openrouter": ["openai/gpt-4o", "anthropic/claude-3-opus"]
}

def detect_provider(api_key):
    for pattern, provider, default_model in PROVIDER_PATTERNS:
        if pattern.match(api_key.strip()):
            return provider, default_model
    return "unknown", "unknown"

def check_key_health(provider, api_key):
    """Gửi yêu cầu kiểm tra đơn giản đến endpoint /models hoặc /chat/completions"""
    try:
        if provider == "google":
            # Gemini: gọi list models (không tốn credit)
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            resp = requests.get(url, timeout=10)
            return resp.status_code == 200
        elif provider in MODEL_ENDPOINTS:
            headers = {"Authorization": f"Bearer {api_key}"}
            resp = requests.get(MODEL_ENDPOINTS[provider], headers=headers, timeout=10)
            return resp.status_code == 200
        else:
            # Generic: chỉ kiểm tra cú pháp
            return len(api_key) > 10
    except:
        return False

def discover_models(provider, api_key):
    """Lấy danh sách model hỗ trợ, fallback nếu lỗi"""
    if provider in MODEL_ENDPOINTS:
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            resp = requests.get(MODEL_ENDPOINTS[provider], headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if provider == "openai" and "data" in data:
                    return [m["id"] for m in data["data"] if "gpt" in m["id"]]
                elif provider == "groq" and "data" in data:
                    return [m["id"] for m in data["data"]]
                elif provider == "openrouter":
                    return [m["id"] for m in data.get("data", [])]
        except:
            pass
    return FALLBACK_MODELS.get(provider, ["unknown-model"])

def refine_key(raw_key):
    """Xử lý một api_keys_raw document"""
    raw_id = raw_key["_id"]
    if already_processed(WORKER, str(raw_id)):
        return

    api_key = raw_key.get("key", "")
    name = raw_key.get("name", "unnamed")
    provider, default_model = detect_provider(api_key)

    # Kiểm tra health
    is_alive = check_key_health(provider, api_key)
    health_score = 100 if is_alive else 0

    if not is_alive:
        db.api_keys_raw.update_one(
            {"_id": raw_id},
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
