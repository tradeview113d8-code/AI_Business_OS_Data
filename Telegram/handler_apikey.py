from datetime import datetime
from Core.mongo import db
from Core.event_bus import publish, EventType
from Core.audit import audit

def init_apikey_handler(bot, handle_main_menu):
    def ask_key_name(message):
        try:
            msg = bot.reply_to(message, "🎯 **Bước 1:** Nhập TÊN GỢI NHỚ cho API Key (Ví dụ: `Gemini_Free`):", parse_mode="Markdown")
            bot.register_next_step_handler(msg, ask_key_value)
        except Exception as e:
            bot.reply_to(message, f"❌ Lỗi: {e}")

    def ask_key_value(message):
        try:
            key_name = message.text.strip() if message.text else ""
            if key_name.startswith("/") or "💡" in key_name or "🔑" in key_name:
                bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
                handle_main_menu(message)
                return

            msg = bot.reply_to(message, f"🔑 **Bước 2:** Hãy dán chuỗi **API Key thô** cho `{key_name}`:", parse_mode="Markdown")
            bot.register_next_step_handler(msg, save_raw_key_handler, key_name)
        except Exception as e:
            bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
            bot.reply_to(message, f"❌ Lỗi: {e}")

    def save_raw_key_handler(message, key_name):
        try:
            raw_key = message.text.strip() if message.text else ""
            if not raw_key or raw_key.startswith("/") or "💡" in raw_key:
                bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
                bot.reply_to(message, "❌ Đã hủy nạp Key do lỗi dữ liệu.")
                return

            key_id = db.api_keys_raw.insert_one({
                "name":       key_name,
                "key":        raw_key,
                "status":     "raw",
                "created_by": message.from_user.id,
                "created_at": datetime.utcnow()
            }).inserted_id
            
            publish(EventType.REQUEST_RECEIVED, "bot", {"action": "raw_key_added", "key_id": str(key_id)})
            audit(message.from_user.id, "add_raw_key", key_id)
            
            bot.reply_to(message, f"✅ **Nạp thành công Key**\nTên: `{key_name}`\nID: `{key_id}`", parse_mode="Markdown")
        except Exception as e:
            bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
            bot.reply_to(message, f"❌ Lỗi: {e}")

    return ask_key_name
  
