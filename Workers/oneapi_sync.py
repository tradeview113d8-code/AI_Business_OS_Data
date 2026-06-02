# Workers/oneapi_sync.py
# ==================================================
# Đồng bộ api_keys_refined -> api_channels
# ==================================================
from pathlib import Path
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from Core.mongo import db
from Core.event_bus import publish, EventType
from Core.logger import log_event
from Core.idempotency import already_processed, mark_processed

WORKER = "oneapi_sync"

def sync_channels():
    """Sync refined keys to api_channels"""
    try:
        refined_keys = list(db.api_keys_refined.find({"status": "active"}))
        
        if not refined_keys:
            log_event(WORKER, "INFO", "No active refined keys to sync")
            return
        
        created_count = 0
        for refined in refined_keys:
            try:
                key_id = refined.get("_id")
                if not key_id:
                    log_event(WORKER, "WARNING", "Refined key missing _id")
                    continue
                
                if already_processed(WORKER, str(key_id)):
                    continue

                raw_key_id = refined.get("raw_key_id")
                provider = refined.get("provider")
                models = refined.get("supported_models", [])

                if not raw_key_id or not provider:
                    log_event(WORKER, "WARNING", f"Refined key missing raw_key_id or provider: {key_id}")
                    mark_processed(WORKER, str(key_id))
                    continue

                if not models:
                    log_event(WORKER, "WARNING", f"No models found for {raw_key_id}")
                    mark_processed(WORKER, str(key_id))
                    continue

                for model in models:
                    try:
                        channel_doc = {
                            "raw_key_id": raw_key_id,
                            "provider": provider,
                            "model": model,
                            "enabled": True,
                            "weight": 1,
                            "last_sync_at": datetime.utcnow()
                        }
                        result = db.api_channels.update_one(
                            {"raw_key_id": raw_key_id, "model": model},
                            {"$set": channel_doc},
                            upsert=True
                        )
                        if result.upserted_id:
                            created_count += 1
                            publish(EventType.CHANNEL_CREATED, WORKER, {
                                "channel_id": str(result.upserted_id),
                                "provider": provider,
                                "model": model
                            })
                            log_event(WORKER, "INFO", f"Created channel {provider}/{model}")
                    except Exception as e:
                        log_event(WORKER, "ERROR", f"Error creating channel for model {model}: {str(e)}")

                mark_processed(WORKER, str(key_id))
            
            except Exception as e:
                log_event(WORKER, "ERROR", f"Error processing refined key: {str(e)}")

        # Vô hiệu hóa channel cũ không còn active
        try:
            active_raw_ids = [r.get("raw_key_id") for r in refined_keys if r.get("raw_key_id")]
            if active_raw_ids:
                result = db.api_channels.update_many(
                    {"raw_key_id": {"$nin": active_raw_ids}, "enabled": True},
                    {"$set": {"enabled": False, "disabled_at": datetime.utcnow()}}
                )
                if result.modified_count > 0:
                    log_event(WORKER, "INFO", f"Disabled {result.modified_count} old channels")
        except Exception as e:
            log_event(WORKER, "ERROR", f"Error disabling old channels: {str(e)}")

        log_event(WORKER, "INFO", f"Sync complete - created/updated {created_count} channels")

    except Exception as e:
        log_event(WORKER, "ERROR", f"Sync channels failed: {str(e)}")

def run():
    """Main worker loop"""
    sync_channels()

if __name__ == "__main__":
    run()
