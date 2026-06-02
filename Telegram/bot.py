from pathlib import Path
import sys
import os
import json
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(override=True)

import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime

# Load config
from Core.config import TELEGRAM_TOKEN
from Core.mongo import db
from Telegram.auth import is_admin
from Telegram.rate_limiter import rate_limit

# Validate token
if not TELEGRAM_TOKEN:
    print("❌ ERROR: TELEGRAM_TOKEN not configured!")
    print("Please add TELEGRAM_TOKEN or TELEGRAM_BOT_TOKEN to .env")
    exit(1)

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def check_auth(message):
    """Check rate limit and admin authorization"""
    if not rate_limit(message.from_user.id):
        bot.reply_to(message, "⏳ Hệ thống đang bận, vui lòng thử lại sau.")
        return False
    if not is_admin(message.from_user.id):
        bot.reply_to(message, f"⛔️ Từ chối: Bạn không có quyền Admin (ID: {message.from_user.id})")
        return False
    return True

def get_main_menu():
    """Get main keyboard menu"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("💡 Thêm Ý Tưởng"), KeyboardButton("🚀 Triển Khai (Deploy)"))
    markup.add(KeyboardButton("📊 Thống Kê"), KeyboardButton("⚙️ Quản Trị Hệ Thống"))
    return markup

def audit(user_id, action, target_id, metadata=None):
    """Log audit event to database"""
    try:
        db.audit_logs.insert_one({
            "user_id": user_id,
            "action": action,
            "target_id": str(target_id),
            "metadata": metadata or {},
            "timestamp": datetime.utcnow()
        })
    except Exception as e:
        print(f"Warning: Error logging audit: {e}")

# ==========================================
# Command Handlers
# ==========================================

@bot.message_handler(commands=['start', 'menu'])
def start(message):
    """Start command - show main menu"""
    if not check_auth(message):
        return
    bot.send_message(message.chat.id, "🤖 AI BUSINESS OS V5.1 - ONLINE", reply_markup=get_main_menu())

@bot.message_handler(func=lambda m: m.text == "🚀 Triển Khai (Deploy)")
def deploy(message):
    """Deploy button handler"""
    if not check_auth(message):
        return
    try:
        from Core.job_queue import create_job
        job = create_job("github_sync", {"action": "manual_deploy", "user": message.from_user.username})
        bot.reply_to(message, f"✅ Đã tạo Job triển khai mới: {job.inserted_id}")
        audit(message.from_user.id, "deploy_request", job.inserted_id)
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

@bot.message_handler(func=lambda m: m.text == "📊 Thống Kê")
def stats(message):
    """Statistics button handler"""
    if not check_auth(message):
        return
    try:
        from Core.job_queue import queue_stats
        s = queue_stats()
        bot.reply_to(message, f"📊 Trạng thái Queue:\n- Đang chờ: {s['pending']}\n- Đang xử lý: {s['processing']}\n- Hoàn tất: {s['completed']}")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

@bot.message_handler(commands=['schedule'])
def schedule_task(message):
    """Schedule a task with JSON payload"""
    if not check_auth(message):
        return
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(message, "❌ Format: /schedule <type> <json_payload>")
            return
        
        payload = json.loads(parts[2])
        db.scheduled_tasks.insert_one({
            "type": parts[1],
            "payload": payload,
            "status": "pending",
            "created_by": message.from_user.id,
            "created_at": datetime.utcnow()
        })
        bot.reply_to(message, "✅ Đã lập lịch tác vụ an toàn.")
        audit(message.from_user.id, "schedule_task", parts[1], {"payload": payload})
    except json.JSONDecodeError:
        bot.reply_to(message, "❌ L���i JSON: Vui lòng kiểm tra format payload")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

# ==========================================
# /apikey - Add API Key Flow
# ==========================================

@bot.message_handler(commands=["apikey"])
def apikey(message):
    """Start API key addition flow"""
    if not check_auth(message):
        return
    msg = bot.reply_to(message, "🔑 Nhập tên gợi nhớ cho API Key (VD: Gemini_Free_01):")
    bot.register_next_step_handler(msg, get_key_name)

def get_key_name(message):
    """Get API key name from user"""
    name = message.text.strip()
    if not name or len(name) < 2:
        bot.reply_to(message, "❌ Tên không hợp lệ (tối thiểu 2 ký tự). Hãy dùng /apikey để thử lại.")
        return
    msg = bot.reply_to(message, f"📎 Dán API Key cho **{name}**:")
    bot.register_next_step_handler(msg, lambda m: save_api_key(m, name))

def save_api_key(message, name):
    """Save API key to database"""
    api_key = message.text.strip()
    if len(api_key) < 10:
        bot.reply_to(message, "❌ API Key quá ngắn (tối thiểu 10 ký tự), không hợp lệ.")
        return
    
    try:
        doc = {
            "name": name,
            "key": api_key,
            "status": "raw",
            "source": "telegram",
            "created_by": message.from_user.id,
            "created_at": datetime.utcnow()
        }
        result = db.api_keys_raw.insert_one(doc)
        
        # Publish event for worker to process
        from Core.event_bus import publish, EventType
        publish(EventType.API_KEY_RAW_ADDED, "bot", {"key_id": str(result.inserted_id)})
        
        # Log audit trail
        audit(message.from_user.id, "add_api_key", result.inserted_id, {"name": name})
        
        bot.reply_to(message, f"✅ Đã nhận API Key **{name}**. Hệ thống sẽ tự động kiểm tra và đồng bộ.")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi khi lưu API Key: {str(e)}")
        print(f"Error saving API key: {e}")

# ==========================================
# Main Loop
# ==========================================

if __name__ == "__main__":
    print("🤖 Bot is starting...")
    print(f"✓ Telegram Token: {'Loaded' if TELEGRAM_TOKEN else 'MISSING'}")
    try:
        print("🚀 Bot is polling for messages...")
        bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print(f"❌ Bot error: {e}")
        raise
