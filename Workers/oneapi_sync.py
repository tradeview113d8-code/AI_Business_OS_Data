from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests
from datetime import datetime
from Core.mongo import db
from Core.logger import log_event
from Core.health import heartbeat

WORKER = "oneapi_sync"

# Endpoint test nhẹ cho từng provider
TEST_ENDPOINTS = {
    "openrouter": {
        "url":     "https://openrouter.ai/api/v1/models",
        "headers": lambda k: {"Authorization": f"Bearer {k}"},
        "method":  "GET",
        "params":  lambda k: {}
    },
    "openai": {
        "url":     "https://api.openai.com/v1/models",
        "headers": lambda k: {"Authorization": f"Bearer {k}"},
        "method":  "GET",
        "params":  lambda k: {}
    },
    "anthropic": {
        "url":     "https://api.anthropic.com/v1/models",
        "headers": lambda k: {
            "x-api-key":         k,
            "anthropic-version": "2023-06-01"
        },
        "method": "GET",
        "params": lambda k: {}
    },
    "gemini": {
        "url":     "https://generativelanguage.googleapis.com/v1/models",
        "headers": lambda k: {},
        "method":  "GET",
        "params":  lambda k: {"key": k}
    },
    "groq": {
        "url":     "https://api.groq.com/openai/v1/models",
        "headers": lambda k: {"Authorization": f"Bearer {k}"},
        "method":  "GET",
        "params":  lambda k: {}
    },
}


def test_key(provider: str, key: str) -> dict:
    endpoint = TEST_ENDPOINTS.get(provider)
    if not endpoint:
        return {"valid": True, "error": "provider_not_tested", "latency_ms": 0}

    try:
        import time
        start   = time.time()
        resp    = requests.request(
            method  = endpoint["method"],
            url     = endpoint["url"],
            headers = endpoint["headers"](key),
            params  = endpoint["params"](key),
            timeout = 10
        )
        latency = int((time.time() - start) * 1000)

        if resp.status_code in [200, 201]:
            return {"valid": True,  "error": None,                       "latency_ms": latency}
        elif resp.status_code == 401:
            return {"valid": False, "error": "unauthorized_401",          "latency_ms": latency}
        elif resp.status_code == 429:
            return {"valid": True,  "error": "rate_limited_429",          "latency_ms": latency}
        else:
            return {"valid": False, "error": f"http_{resp.status_code}",  "latency_ms": latency}

    except requests.Timeout:
        return {"valid": False, "error": "timeout",  "latency_ms": 10000}
    except Exception as e:
        return {"valid": False, "error": str(e)[:80], "latency_ms": 0}


def run():
    heartbeat(WORKER)
    tested  = 0
    valid   = 0
    invalid = 0

    keys = list(db.api_key_vault.find({"status": {"$in": ["active", "error"]}}))

    if not keys:
        print("oneapi_sync: no keys to test")
        return

    for vault_key in keys:
        provider = vault_key.get("provider", "unknown")
        raw_key  = vault_key.get("key", "")
        key_name = vault_key.get("name", provider)

        if not raw_key:
            continue

        result  = test_key(provider, raw_key)
        tested += 1

        update = {
            "last_tested":  datetime.utcnow(),
            "last_latency": result["latency_ms"],
            "last_error":   result["error"]
        }

        if result["valid"]:
            update["status"]      = "active"
            update["error_count"] = 0
            valid += 1
            print(f"[OK]  {key_name} ({provider}) — {result['latency_ms']}ms")
        else:
            error_count = vault_key.get("error_count", 0) + 1
            update["error_count"] = error_count

            if error_count >= 3:
                update["status"] = "disabled"
                db.api_keys.update_one(
                    {"name": key_name},
                    {"$set": {"status": "disabled", "disabled_reason": result["error"]}}
                )
                db.notifications.insert_one({
                    "message":    f"🔑 API Key bị vô hiệu hoá: {key_name} ({provider}) — {result['error']}",
                    "sent":       False,
                    "created_at": datetime.utcnow()
                })
                print(f"[DISABLED] {key_name} ({provider}) — {result['error']}")
            else:
                update["status"] = "error"
                print(f"[ERR] {key_name} ({provider}) — {result['error']} ({error_count}/3)")

            invalid += 1

        db.api_key_vault.update_one(
            {"_id": vault_key["_id"]},
            {"$set": update}
        )
        log_event(WORKER, "INFO" if result["valid"] else "WARN",
                  f"{key_name} valid={result['valid']} latency={result['latency_ms']}ms")

    print(f"oneapi_sync done: tested={tested} valid={valid} invalid={invalid}")
    log_event(WORKER, "INFO", f"done tested={tested} valid={valid} invalid={invalid}")


if __name__ == "__main__":
    run()
    
