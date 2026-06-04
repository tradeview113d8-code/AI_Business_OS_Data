import os
import sys
import threading
from pathlib import Path
from datetime import datetime
from flask import Flask

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

try:
    from Core.mongo import db
    from Core.config import TELEGRAM_TOKEN
    from Core.job_queue import queue_stats, create_job
    from Core.event_bus import publish, EventType, pending_count
    from Core.audit import audit
    from Telegram.auth import is_admin
    from Telegram.rate_limiter import rate_limit
    
    # IMPORT CÁC TRƯỞNG PHÒNG (MODULE CON)
    from Telegram.handler_cookie import init_cookie_handler
    from Telegram.handler_apikey import init_apikey_handler
except ImportError as e:
    print(f"❌ Lỗi Import thư viện: {e}")
    sys.exit(1)

web_app = Flask(__name__)
@web_app.route('/')
def home(): return "🤖 AI Business OS V5 - Telegram Commander đang hoạt động 24/7!"
def run_web():
    port = int(os.environ.get("PORT", 8080))
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    web_app.run(host="0.0.0.0", port=port)

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def check_permission(message):
    if not rate_limit(message.from_user.id):
        bot.reply_to(message, "⏳ Chống spam...")
        return False
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔️ Không có quyền truy cập.")
        return False
    return True

# MENU MỚI CÓ THÊM NÚT NẠP COOKIE
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("💡 Thêm Ý Tưởng"), KeyboardButton("🚀 Triển Khai (Deploy)"))
    markup.add(KeyboardButton("🔑 Nạp API Key"), KeyboardButton("🍪 Nạp Cookie MXH"))
    markup.add(KeyboardButton("📊 Thống Kê"), KeyboardButton("⚙️ Menu Quản Trị"))
    return markup

@bot.message_handler(commands=["start"])
def start(message):
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    if not check_permission(message): return
    bot.send_message(message.chat.id, "🤖 **AI BUSINESS OS V5**\nVui lòng chọn tác vụ:", reply_markup=get_main_menu(), parse_mode="Markdown")

# ĐĂNG KÝ CÁC MODULE CON
handle_apikey_flow = init_apikey_handler(bot, start)
handle_cookie_flow = init_cookie_handler(bot, start)

@bot.message_handler(func=lambda message: True)
def handle_main_menu(message):
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    if not check_permission(message): return
    text = message.text
    
    # CHIA VIỆC CHO CÁC MODULE CON
    if text == "🔑 Nạp API Key":
        handle_apikey_flow(message)
    elif text == "🍪 Nạp Cookie MXH":
        handle_cookie_flow(message)
    elif text == "💡 Thêm Ý Tưởng":
        # (Tạm giữ hàm này trong file cha cho gọn, Giám đốc có thể tách ra sau)
        msg = bot.reply_to(message, "📝 Nhập Ý tưởng thô:")
        bot.register_next_step_handler(msg, lambda m: save_idea(m))
    elif text == "⚙️ Menu Quản Trị":
        bot.send_message(message.chat.id, "🛠 **Đang xây dựng Menu Admin...**", parse_mode="Markdown")

def save_idea(message):
    try:
        request_id = db.requests.insert_one({"prompt": message.text, "status": "new", "created_at": datetime.utcnow()}).inserted_id
        publish(EventType.REQUEST_RECEIVED, "bot", {"request_id": str(request_id)})
        bot.reply_to(message, f"✅ Đã lưu ý tưởng. ID: `{request_id}`", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}")

if __name__ == "__main__":
    print("🚀 Khởi động Web Server...")
    threading.Thread(target=run_web, daemon=True).start()
    print("🚀 Khởi động Bot Telegram...")
    bot.infinity_polling(skip_pending=True)
