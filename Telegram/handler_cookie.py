from datetime import datetime
from Core.mongo import db
from Core.event_bus import publish, EventType
from Core.audit import audit

def start_cookie_flow(bot, message, router_fallback):
    msg = bot.reply_to(message, "🎯 Nền tảng của Cookie? (VD: `Facebook`):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, lambda m: ask_cookie(bot, m, router_fallback))

def ask_cookie(bot, message, router_fallback):
    plat = message.text.strip() if message.text else ""
    if plat.startswith("/") or "🍪" in plat: return router_fallback(message)
    msg = bot.reply_to(message, f"🍪 Dán Cookie/Proxy cho `{plat}`:")
    bot.register_next_step_handler(msg, lambda m: save_cookie(bot, m, plat, router_fallback))

def save_cookie(bot, message, plat, router_fallback):
    val = message.text.strip() if message.text else ""
    if not val or "🍪" in val: return router_fallback(message)
    
    cid = db.social_acc_raw.insert_one({"platform": plat, "cookie": val, "status": "raw", "created_by": message.from_user.id, "created_at": datetime.utcnow()}).inserted_id
    publish(EventType.REQUEST_RECEIVED, "bot", {"action": "raw_cookie_added", "cookie_id": str(cid)})
    audit(message.from_user.id, "add_raw_cookie", cid)
    bot.reply_to(message, f"✅ Đã nạp Cookie `{plat}` vào kho thô.")
    
