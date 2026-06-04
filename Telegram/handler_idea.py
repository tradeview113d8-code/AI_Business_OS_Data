from datetime import datetime
from Core.mongo import db
from Core.job_queue import create_job
from Core.event_bus import publish, EventType
from Core.audit import audit

def start_idea_flow(bot, message, router_fallback):
    msg = bot.reply_to(message, "📝 Nhập Yêu cầu / Ý tưởng thô mới của sếp:")
    bot.register_next_step_handler(msg, lambda m: save_idea(bot, m, router_fallback))

def save_idea(bot, message, router_fallback):
    text = message.text.strip() if message.text else ""
    if text.startswith("/") or "💡" in text or "⚙️" in text:
        router_fallback(message)
        return
        
    try:
        request_id = db.requests.insert_one({
            "prompt": text, "status": "new",
            "created_by": message.from_user.id, "created_at": datetime.utcnow()
        }).inserted_id
        
        create_job("analyze_request", {"request_id": str(request_id)}, created_by=message.from_user.id)
        publish(EventType.REQUEST_RECEIVED, "bot", {"request_id": str(request_id)})
        audit(message.from_user.id, "create_request", request_id)
        
        bot.reply_to(message, f"✅ **Đã nạp Ý tưởng**\nID: `{request_id}`", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}")

