from pathlib import Path
import sys
import os
import json
from dotenv import load_dotenv # Added load_dotenv here explicitly

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(override=True) # Ensure dotenv is loaded early

import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
from Core.mongo import db
from Core.job_queue import create_job, queue_stats
from Telegram.auth import is_admin
from Telegram.rate_limiter import rate_limit

TOKEN = os.getenv('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)

def check_auth(message):
    if not rate_limit(message.from_user.id):
        bot.reply_to(message, "⏳ Hệ thống đang bận, vui lòng thử lại sau.")
        return False
    if not is_admin(message.from_user.id):
        bot.reply_to(message, f"⛔️ Từ chối: Bạn không có quyền Admin (ID: {message.from_user.id})")
        return False
    return True

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("💡 Thêm Ý Tưởng"), KeyboardButton("🚀 Triển Khai (Deploy)"))
    markup.add(KeyboardButton("📊 Thống Kê"), KeyboardButton("⚙️ Quản Trị Hệ Thống"))
    return markup

@bot.message_handler(commands=['start', 'menu'])
def start(message):
    if not check_auth(message): return
    bot.send_message(message.chat.id, "🤖 AI BUSINESS OS V5.1 - ONLINE", reply_markup=get_main_menu())

@bot.message_handler(func=lambda m: m.text == "🚀 Triển Khai (Deploy)")
def deploy(message):
    if not check_auth(message): return
    job = create_job("github_sync", {"action": "manual_deploy", "user": message.from_user.username})
    bot.reply_to(message, f"✅ Đã tạo Job triển khai mới: {job.inserted_id}")

@bot.message_handler(func=lambda m: m.text == "📊 Thống Kê")
def stats(message):
    if not check_auth(message): return
    s = queue_stats()
    bot.reply_to(message, f"📊 Trạng thái Queue:\n- Đang chờ: {s['pending']}\n- Đang xử lý: {s['processing']}\n- Hoàn tất: {s['completed']}")

@bot.message_handler(commands=['schedule'])
def schedule_task(message):
    if not check_auth(message): return
    try:
        # V5.1 Security Patch: Use json.loads instead of eval
        parts = message.text.split(maxsplit=2)
        payload = json.loads(parts[2])
        db.scheduled_tasks.insert_one({"type": parts[1], "payload": payload, "status": "pending"})
        bot.reply_to(message, "✅ Đã lập lịch tác vụ an toàn.")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi format: {str(e)}")

print("Bot logic updated (V5.1) and starting...")
bot.infinity_polling(skip_pending=True)
