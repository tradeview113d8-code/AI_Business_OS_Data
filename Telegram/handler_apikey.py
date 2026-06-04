from datetime import datetime
from Core.mongo import db
from Core.event_bus import publish, EventType
from Core.audit import audit

def start_apikey_flow(bot, message, router_fallback):
    msg = bot.reply_to(message, "🎯 Nhập TÊN API Key (VD: `Gemini_Free`):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, lambda m: ask_value(bot, m, router_fallback))

def ask_value(bot, message, router_fallback):
    name = message.text.strip() if message.text else ""
    if name.startswith("/") or "🔑" in name: return router_fallback(message)
    msg = bot.reply_to(message, f"🔑 Dán chuỗi API Key cho `{name}`:")
    bot.register_next_step_handler(msg, lambda m: save_key(bot, m, name, router_fallback))

def save_key(bot, message, name, router_fallback):
    val = message.text.strip() if message.text else ""
    if not val or "🔑" in val: return router_fallback(message)
    
    kid = db.api_keys_raw.insert_one({"name": name, "key": val, "status": "raw", "created_by": message.from_user.id, "created_at": datetime.utcnow()}).inserted_id
    publish(EventType.REQUEST_RECEIVED, "bot", {"action": "raw_key_added", "key_id": str(kid)})
    audit(message.from_user.id, "add_raw_key", kid)
    bot.reply_to(message, f"✅ Đã nạp Key `{name}` vào kho thô.")
