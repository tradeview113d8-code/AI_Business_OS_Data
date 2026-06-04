from datetime import datetime
from Core.mongo import db
from Core.event_bus import publish, EventType
from Core.audit import audit

def init_cookie_handler(bot, handle_main_menu):
    def ask_cookie_platform(message):
        try:
            msg = bot.reply_to(message, "🎯 **Bước 1:** Nền tảng của Cookie này là gì? (Ví dụ: `Facebook`, `TikTok`, `X`):", parse_mode="Markdown")
            bot.register_next_step_handler(msg, ask_cookie_value)
        except Exception as e:
            bot.reply_to(message, f"❌ Lỗi: {e}")

    def ask_cookie_value(message):
        try:
            platform = message.text.strip() if message.text else ""
            if platform.startswith("/") or "💡" in platform or "🔑" in platform:
                bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
                handle_main_menu(message)
                return

            msg = bot.reply_to(message, f"🍪 **Bước 2:** Hãy dán chuỗi **Cookie** cho `{platform}` (Có thể kèm IP Proxy nếu có):", parse_mode="Markdown")
            bot.register_next_step_handler(msg, save_raw_cookie_handler, platform)
        except Exception as e:
            bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
            bot.reply_to(message, f"❌ Lỗi: {e}")

    def save_raw_cookie_handler(message, platform):
        try:
            raw_cookie = message.text.strip() if message.text else ""
            if not raw_cookie or raw_cookie.startswith("/") or "💡" in raw_cookie:
                bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
                bot.reply_to(message, "❌ Đã hủy nạp Cookie do lỗi dữ liệu.")
                return

            cookie_id = db.social_acc_raw.insert_one({
                "platform":   platform,
                "cookie":     raw_cookie,
                "status":     "raw",
                "created_by": message.from_user.id,
                "created_at": datetime.utcnow()
            }).inserted_id
            
            # Quăng sự kiện lên băng chuyền cho account_refiner xử lý sau
            publish(EventType.REQUEST_RECEIVED, "bot", {"action": "raw_cookie_added", "cookie_id": str(cookie_id)})
            audit(message.from_user.id, "add_raw_cookie", cookie_id)
            
            bot.reply_to(message, f"✅ **Nạp Cookie Thành Công**\nNền tảng: `{platform}`\nID: `{cookie_id}`\n⏳ *Hệ thống sẽ kiểm định Cookie này sau.*", parse_mode="Markdown")
        except Exception as e:
            bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
            bot.reply_to(message, f"❌ Lỗi: {e}")

    return ask_cookie_platform
  
