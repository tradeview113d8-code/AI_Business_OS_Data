import os, sys, threading
from pathlib import Path
from flask import Flask
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from Core.config import TELEGRAM_TOKEN
from Telegram.auth import is_admin
from Telegram.rate_limiter import rate_limit

# --- GỌI CÁC TRƯỞNG PHÒNG (MODULES) ---
from Telegram.handler_idea import start_idea_flow
from Telegram.handler_apikey import start_apikey_flow
from Telegram.handler_cookie import start_cookie_flow
from Telegram.handler_stats import handle_stats, handle_report
from Telegram.handler_admin import show_admin_menu, handle_deploy, register_admin_callbacks

# --- MÁY CHỦ WEB CHỐNG NGỦ ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "🤖 AI Business OS V5 - Router đang hoạt động!"
def run_web():
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    web_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# --- KHỞI TẠO BOT ---
bot = telebot.TeleBot(TELEGRAM_TOKEN)
register_admin_callbacks(bot) # Đăng ký sự kiện nút bấm Admin

def check_permission(message):
    if not rate_limit(message.from_user.id): return False
    if not is_admin(message.from_user.id): return False
    return True

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("💡 Thêm Ý Tưởng"), KeyboardButton("🚀 Triển Khai (Deploy)"))
    markup.add(KeyboardButton("📊 Thống Kê"), KeyboardButton("📑 Xem Báo Cáo"))
    markup.add(KeyboardButton("🔑 Nạp API Key"), KeyboardButton("🍪 Nạp Cookie MXH"))
    markup.add(KeyboardButton("⚙️ Menu Quản Trị (Admin)"))
    return markup

# --- BỘ ĐỊNH TUYẾN CHÍNH (ROUTER) ---
@bot.message_handler(commands=["start"])
def start(message):
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    if check_permission(message):
        bot.send_message(message.chat.id, "🤖 **HỆ ĐIỀU HÀNH AI V5**\nVui lòng chọn tác vụ:", reply_markup=get_main_menu(), parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def router(message):
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    if not check_permission(message): return
    
    # CHUYỂN GIAO CÔNG VIỆC CHO CÁC FILE CON
    t = message.text
    if t == "💡 Thêm Ý Tưởng":         start_idea_flow(bot, message, router)
    elif t == "🚀 Triển Khai (Deploy)": handle_deploy(bot, message)
    elif t == "📊 Thống Kê":            handle_stats(bot, message)
    elif t == "📑 Xem Báo Cáo":         handle_report(bot, message)
    elif t == "🔑 Nạp API Key":         start_apikey_flow(bot, message, router)
    elif t == "🍪 Nạp Cookie MXH":      start_cookie_flow(bot, message, router)
    elif t == "⚙️ Menu Quản Trị (Admin)": show_admin_menu(bot, message)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    bot.infinity_polling(skip_pending=True)
    
