import os
import sys
import threading
from pathlib import Path
from datetime import datetime
from flask import Flask

# Đảm bảo nhận diện thư mục hệ thống
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Gọi các Module lõi V5
try:
    from Core.mongo import db
    from Core.config import TELEGRAM_TOKEN
    from Core.job_queue import create_job, queue_stats
    from Core.event_bus import publish, EventType, pending_count
    from Core.audit import audit
    from Telegram.auth import is_admin
    from Telegram.rate_limiter import rate_limit
except ImportError as e:
    print(f"❌ Lỗi Import thư viện lõi: {e}")
    sys.exit(1)

# ==========================================
# 🌐 1. MÁY CHỦ WEB GIẢ (CHỐNG NGỦ)
# ==========================================
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "🤖 AI Business OS V5 - Telegram Commander đang hoạt động 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    web_app.run(host="0.0.0.0", port=port)

# ==========================================
# 🤖 2. KHỞI TẠO BOT & BẢO MẬT
# ==========================================
bot = telebot.TeleBot(TELEGRAM_TOKEN)

def check_permission(message):
    if not rate_limit(message.from_user.id):
        bot.reply_to(message, "⏳ Hệ thống chống spam đang kích hoạt...")
        return False
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔️ Bạn không có quyền truy cập hệ thống này.")
        return False
    return True

# ==========================================
# 🛠 3. MENU GIAO DIỆN
# ==========================================
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("💡 Thêm Ý Tưởng"),
        KeyboardButton("🚀 Triển Khai (Deploy)")
    )
    markup.add(
        KeyboardButton("📊 Thống Kê"),
        KeyboardButton("📑 Xem Báo Cáo")
    )
    markup.add(
        KeyboardButton("🔑 Nạp API Key"),
        KeyboardButton("⚙️ Menu Quản Trị (Admin)")
    )
    return markup

def get_admin_inline_menu():
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("📋 Danh sách Jobs", callback_data="admin_jobs"),
        InlineKeyboardButton("💀 Dead Jobs", callback_data="admin_dead")
    )
    markup.row(
        InlineKeyboardButton("🚌 Event Bus", callback_data="admin_events"),
        InlineKeyboardButton("🔌 Plugins Registry", callback_data="admin_plugins")
    )
    markup.row(
        InlineKeyboardButton("🩺 Trạng thái Workers", callback_data="admin_health")
    )
    return markup

# ==========================================
# 📡 4. ĐIỀU HƯỚNG LỆNH CHÍNH
# ==========================================
@bot.message_handler(commands=["start"])
def start(message):
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    if not check_permission(message): return
    bot.send_message(
        message.chat.id, 
        "🤖 **AI BUSINESS OS V5 ONLINE**\n\nVui lòng chọn tác vụ điều phối bên dưới:", 
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: message.text in [
    "💡 Thêm Ý Tưởng", "🚀 Triển Khai (Deploy)", "📊 Thống Kê", "📑 Xem Báo Cáo", "🔑 Nạp API Key", "⚙️ Menu Quản Trị (Admin)"
])
def handle_main_menu(message):
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    if not check_permission(message): return
    
    text = message.text
    if text == "💡 Thêm Ý Tưởng":
        idea(message)
    elif text == "🚀 Triển Khai (Deploy)":
        deploy_job(message)
    elif text == "📊 Thống Kê":
        stats(message)
    elif text == "📑 Xem Báo Cáo":
        report(message)
    elif text == "🔑 Nạp API Key":
        ask_key_name(message)
    elif text == "⚙️ Menu Quản Trị (Admin)":
        bot.send_message(
            message.chat.id, 
            "🛠 **Khu vực quản trị:**", 
            reply_markup=get_admin_inline_menu(),
            parse_mode="Markdown"
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def handle_admin_callbacks(call):
    if not is_admin(call.from_user.id): return
    
    action = call.data
    if action == "admin_jobs":
        jobs_list(call.message)
    elif action == "admin_dead":
        dead_jobs(call.message)
    elif action == "admin_events":
        event_bus_status(call.message)
    elif action == "admin_plugins":
        plugins_list(call.message)
    elif action == "admin_health":
        workers_health(call.message)
        
    bot.answer_callback_query(call.id)

# ==========================================
# 📥 5. LUỒNG THÊM Ý TƯỞNG
# ==========================================
def idea(message):
    try:
        msg = bot.reply_to(message, "📝 Nhập Yêu cầu / Ý tưởng thô mới của sếp:")
        bot.register_next_step_handler(msg, save_request)
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}")

def save_request(message):
    try:
        prompt_text = message.text.strip() if message.text else ""
        if prompt_text.startswith("/") or prompt_text in ["💡 Thêm Ý Tưởng", "🚀 Triển Khai (Deploy)", "📊 Thống Kê", "📑 Xem Báo Cáo", "🔑 Nạp API Key", "⚙️ Menu Quản Trị (Admin)"]:
            bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
            handle_main_menu(message)
            return

        request_id = db.requests.insert_one({
            "prompt":     prompt_text,
            "status":     "new",
            "created_by": message.from_user.id,
            "created_at": datetime.utcnow()
        }).inserted_id
        
        create_job("analyze_request", {"request_id": str(request_id)}, created_by=message.from_user.id)
        publish(EventType.REQUEST_RECEIVED, "bot", {"request_id": str(request_id)})
        audit(message.from_user.id, "create_request", request_id)
        
        bot.reply_to(message, f"✅ **Đã ghi nhận Ý tưởng**\nID: `{request_id}`", parse_mode="Markdown")
    except Exception as e:
        bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
        bot.reply_to(message, f"❌ Lỗi: {e}")

# ==========================================
# 🔑 6. LUỒNG NẠP API KEY
# ==========================================
def ask_key_name(message):
    try:
        msg = bot.reply_to(message, "🎯 **Bước 1:** Nhập TÊN GỢI NHỚ cho API Key (Ví dụ: `Gemini_Free`):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, ask_key_value)
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}")

def ask_key_value(message):
    try:
        key_name = message.text.strip() if message.text else ""
        if key_name.startswith("/") or key_name in ["💡 Thêm Ý Tưởng", "🚀 Triển Khai (Deploy)", "📊 Thống Kê", "📑 Xem Báo Cáo", "🔑 Nạp API Key", "⚙️ Menu Quản Trị (Admin)"]:
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
        if not raw_key or raw_key.startswith("/") or raw_key in ["💡 Thêm Ý Tưởng", "🚀 Triển Khai (Deploy)", "📊 Thống Kê", "📑 Xem Báo Cáo", "🔑 Nạp API Key", "⚙️ Menu Quản Trị (Admin)"]:
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

# ==========================================
# 📊 7. CÁC HÀM XỬ LÝ DATABASE ADMIN
# ==========================================
def deploy_job(message):
    job_id = db.jobs.insert_one({"type": "deploy", "status": "pending", "created_at": datetime.utcnow()}).inserted_id
    bot.reply_to(message, f"🚀 **Deploy Job ID:** `{job_id}`", parse_mode="Markdown")

def stats(message):
    try:
        s = queue_stats()
        bot.send_message(message.chat.id, f"📊 Pending: {s.get('pending',0)} | Processing: {s.get('processing',0)} | Done: {s.get('completed',0)}")
    except Exception:
        bot.send_message(message.chat.id, "📊 Hệ thống thống kê đang bảo trì.")

def report(message):
    r = db.reports.find_one(sort=[("created_at", -1)])
    if r:
        bot.send_message(message.chat.id, str(r.get("content", ""))[-3500:])
    else:
        bot.send_message(message.chat.id, "📭 Không có báo cáo.")

def jobs_list(message):
    rows = [f"`{j['_id']}` | {j.get('type','N/A')} | {j.get('status','N/A')}" for j in db.jobs.find().sort("created_at", -1).limit(10)]
    bot.send_message(message.chat.id, "📋 Jobs:\n" + "\n".join(rows) if rows else "📭 Trống", parse_mode="Markdown")

def dead_jobs(message):
    dead_list = list(db.dead_letter_queue.find().sort("failed_at", -1).limit(5))
    rows = [f"❌ `{d.get('job_id')}` - {str(d.get('error'))[:50]}" for d in dead_list]
    bot.send_message(message.chat.id, "💀 Dead Jobs:\n" + "\n".join(rows) if rows else "✅ Trống", parse_mode="Markdown")

def event_bus_status(message):
    rows = [f"`{et}`: {pending_count(et)} pending" for et in ["request_received", "analysis_done", "knowledge_ready", "report_written"]]
    bot.send_message(message.chat.id, "🚌 Event Bus:\n" + "\n".join(rows), parse_mode="Markdown")

def plugins_list(message):
    rows = [f"🔌 {p.get('plugin')} [{p.get('status')}]" for p in db.plugin_registry.find()]
    bot.send_message(message.chat.id, "🔌 Plugins:\n" + "\n".join(rows) if rows else "📭 Trống", parse_mode="Markdown")

def workers_health(message):
    rows = [f"👤 {w.get('worker')} | {w.get('status')}" for w in db.health.find()]
    bot.send_message(message.chat.id, "🩺 Workers:\n" + "\n".join(rows) if rows else "📭 Trống", parse_mode="Markdown")

# ==========================================
# 🚀 8. MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("🚀 Khởi động Web Server ngầm...")
    threading.Thread(target=run_web, daemon=True).start()
    
    print("🚀 Khởi động Bot Telegram...")
    bot.infinity_polling(skip_pending=True)
    
