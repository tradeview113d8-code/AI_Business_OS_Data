import time
from datetime import datetime
from Core.mongo import db
from Core.event_bus import consume_all, ack_event, fail_event
from Core.logger import log_event
from Core.metrics import save_metrics
from Core.health import heartbeat

# ==========================================
# REGISTRY
# ==========================================
# Thêm plugin mới vào đây, không sửa code khác.
#
# Format:
#   "event_type": PluginClass
#
# Plugin class phải implement handle(event) -> None
# ==========================================

_REGISTRY = {}


def register_plugin(event_type, plugin_class):
    """Đăng ký plugin cho event_type."""
    _REGISTRY[event_type] = plugin_class
    db.plugin_registry.update_one(
        {"event_type": event_type},
        {"$set": {
            "event_type":  event_type,
            "plugin":      plugin_class.__name__,
            "status":      "registered",
            "registered_at": datetime.utcnow()
        }},
        upsert=True
    )
    log_event("plugin_registry", "INFO",
              f"registered {plugin_class.__name__} for {event_type}")


def get_plugin(event_type):
    return _REGISTRY.get(event_type)


def run_once():
    """
    Xử lý 1 lần tất cả events có plugin đăng ký.
    Dùng cho GitHub Actions.
    """
    processed = 0
    errors    = 0

    for event_type, plugin_class in _REGISTRY.items():
        heartbeat(f"plugin:{event_type}")
        events = consume_all(event_type, plugin_class.__name__)

        for event in events:
            plugin = plugin_class()
            try:
                plugin.handle(event)
                ack_event(event["_id"])
                processed += 1
                log_event(plugin_class.__name__, "INFO",
                          f"handled {event_type}: {event['_id']}")
            except Exception as e:
                errors += 1
                fail_event(event["_id"], str(e))
                log_event(plugin_class.__name__, "ERROR",
                          f"failed {event_type}: {e}")

    save_metrics("plugin_runner", processed, errors)
    return processed, errors


def run_forever(interval=5):
    """
    Chạy liên tục — dùng cho Oracle/VPS.
    """
    log_event("plugin_registry", "INFO",
              f"run_forever started, interval={interval}s")
    while True:
        try:
            run_once()
        except Exception as e:
            log_event("plugin_registry", "ERROR", f"iteration error: {e}")
        time.sleep(interval)


# ==========================================
# BASE PLUGIN CLASS
# ==========================================

class BasePlugin:
    """
    Repo vệ tinh kế thừa class này.

    Ví dụ:
        class SEOPlugin(BasePlugin):
            def handle(self, event):
                knowledge_id = event["payload"]["knowledge_id"]
                # ... logic riêng ...

        register_plugin(EventType.KNOWLEDGE_READY, SEOPlugin)
    """
    def handle(self, event):
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement handle(event)"
        )
