import os
import sys
import threading
from pathlib import Path
from datetime import datetime
from flask import Flask

# Đồng bộ hóa đường dẫn để nhận diện thư mục Core và Telegram
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Import các thành phần lõi từ V5
from Core.mongo import db
from Core.config import TELEGRAM_TOKEN
from Core.job_queue import create_job, queue_stats
from Core.event_bus import publish, EventType, pending_count
from Core.audit import audit

# Import 2 module phân quyền và chống spam
from Telegram.auth import is_admin
from Telegram.rate_limiter import rate_limit

# ==========================================
# 🌐 1. KHỞI TẠO MÁY CHỦ WEB GIẢ (NGỤY TRANG)
# ==========================================
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "🤖 AI Business OS V5 - Telegram Commander đang hoạt động 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    # Chạy Flask server tắt các thông báo console để không làm rối log của Bot
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    web_app.run(host="0.0.0.0", port=port)

# ==========================================
# 🤖 2. KHỞI TẠO BOT TELEGRAM & BẢO MẬT
# ==========================================
bot = telebot.TeleBot(TELEGRAM_TOKEN)

def check_permission(message):
    if not rate_limit(message.from_user.id):
        bot.reply_to(message, "⏳ Chậm lại một chút, hệ thống đang kích hoạt chống spam...")
        return False
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔️ Bạn không có quyền truy cập hệ thống quản trị này.")
        return False
    return True

# ==========================================
# 🛠 3. CẤU HÌNH GIAO DIỆN NÚT BẤM
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
# 📡 4. BỘ LẮNG NGHE LỆNH CHÍNH
# ==========================================
@bot.message_handler(commands=["start"])
def start(message):
    # Đảm bảo luồng không bị kẹt khi gõ /start
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    if not check_permission(message): return
    bot.send_message(
        message.chat.id, 
        "🤖 **AI BUSINESS OS V5 ONLINE**\n\nHệ thống Core Bus và Dây chuyền Workers đã thông suốt.\nVui lòng chọn tác vụ điều phối bên dưới:", 
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
            "🛠 **Khu vực giám sát & Điều phối kỹ thuật:**", 
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
# 📥 5. LUỒNG NHẬP LIỆU Ý TƯỞNG
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
        
        bot.reply_to(message, f"✅ **Ghi nhận Yêu cầu thành công**\nID: `{request_id}`\n\n*Hàng đợi GitHub Actions sẽ xử lý trong mẻ tiếp theo.*", parse_mode="Markdown")
    except Exception as e:
        bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
        bot.reply_to(message, f"❌ Lỗi xử lý ý tưởng: {e}")

# ==========================================
# 🔑 6. LUỒNG NẠP API KEY BỌC BẢO VỆ TUYỆT ĐỐI
# ==========================================
def ask_key_name(message):
    try:
        msg = bot.reply_to(message, "🎯 **Bước 1:** Nhập TÊN GỢI NHỚ cho API Key (Ví dụ: `Gemini_Free_01`, `Groq_Chính`):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, ask_key_value)
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi khởi động luồng: {e}")

def ask_key_value(message):
    try:
        key_name = message.text.strip() if message.text else ""
        
        if key_name.startswith("/") or key_name in ["💡 Thêm Ý Tưởng", "🚀 Triển Khai (Deploy)", "📊 Thống Kê", "📑 Xem Báo Cáo", "🔑 Nạp API Key", "⚙️ Menu Quản Trị (Admin)"]:
            bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
            handle_main_menu(message)
            return

        msg = bot.reply_to(message, f"🔑 **Bước 2:** Hãy dán chuỗi **API Key thô** của nguồn `{key_name}` vào đây:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, save_raw_key_handler, key_name)
    except Exception as e:
        bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
        bot.reply_to(message, f"❌ Lỗi xử lý bước 1: {e}")

def save_raw_key_handler(message, key_name):
    try:
        raw_key = message.text.strip() if message.text else ""
        
        if not raw_key or raw_key.startswith("/") or raw_key in ["💡 Thêm Ý Tưởng", "🚀 Triển Khai (Deploy)", "📊 Thống Kê", "📑 Xem Báo Cáo", "🔑 Nạp API Key", "⚙️ Menu Quản Trị (Admin)"]:
            bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
            bot.reply_to(message, "❌ Đã hủy bỏ quy trình nạp Key do dữ liệu không hợp lệ.")
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
        
        bot.reply_to(message, f"✅ **Nạp thành công API Key thô**\nTên: `{key_name}`\nID: `{key_id}`\n\n*Worker Key Refiner trên GitHub sẽ tinh chỉnh và quét model khả dụng.*", parse_mode="Markdown")
    except Exception as e:
        bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
        bot.reply_to(message, f"❌ Lỗi xử lý ghi dữ liệu bước 2: {e}")

# ==========================================
# 📊 7. CÁC HÀM TRUY VẤN VÀ THỰC THI (ADMIN)
# ==========================================
def deploy_job(message):
    job_id = db.jobs.insert_one({
        "type": "deploy", 
        "status": "pending", 
        "created_at": datetime.utcnow()
    }).inserted_id
    bot.reply_to(message, f"🚀 **Job Created in MongoDB Successfully:**\nID: `{job_id}`", parse_mode="Markdown")

def stats(message):
    s = queue_stats()
    e_pending = db.events.count_documents({"status": "pending"})
    e_dead    = db.events.count_documents({"status": "dead"})
    bot.send_message(message.chat.id, f"""📊 **TRẠNG THÁI HỆ THỐNG OPERATING SYSTEM**

🔹 **Hàng đợi Tác vụ (Jobs Queues):**
  - Chờ xử lý: `{s.get('pending', 0)}`
  - Đang chạy: `{s.get('processing', 0)}`
  - Hoàn thành: `{s.get('completed', 0)}`
  - Lỗi kẹt (Dead): `{s.get('dead', 0)}`

🔸 **Trục Sự kiện (Event Bus):**
  - Sự kiện chờ: `{e_pending}`
  - Sự kiện lỗi: `{e_dead}`""", parse_mode="Markdown")

def report(message):
    r = db.reports.find_one(sort=[("created_at", -1)])
    if not r:
        bot.send_message(message.chat.id, "📭 Hệ thống chưa có bản báo cáo tri thức nào được xuất bản.")
        return
    content = r.get("content", "")
    bot.send_message(message.chat.id, content[-3500:] if len(content) > 3500 else content)

def jobs_list(message):
    rows = [f"• `{j['_id']}` | {j.get('type','N/A')} | `{j.get('status','N/A')}`" 
            for j in db.jobs.find().sort("created_at", -1).limit(10)]
    bot.send_message(message.chat.id, "📋 **10 Tác vụ gần nhất:**\n\n" + "\n".join(rows) if rows else "📭 Không có Jobs nào.", parse_mode="Markdown")

def dead_jobs(message):
    dead_list = list(db.dead_letter_queue.find().sort("failed_at", -1).limit(5))
    if not dead_list:
        bot.send_message(message.chat.id, "✅ Sạch sẽ! Hệ thống không phát hiện lỗi kẹt tác vụ nào.")
        return
    rows = [f"❌ ID: `{d.get('job_id')}`\nLoại: `{d.get('job_type')}`\nLỗi: `{str(d.get('error'))[:70]}`\n---" for d in dead_list]
    bot.send_message(message.chat.id, "💀 **Danh sách Dead Jobs:**\n\n" + "\n".join(rows), parse_mode="Markdown")

def event_bus_status(message):
    rows = []
    for et in ["request_received", "analysis_done", "knowledge_ready", "report_written", "report_exported"]:
        count = pending_count(et)
        rows.append(f"• `{et}`: **{count}** pending")
    bot.send_message(message.chat.id, "🚌 **Tình trạng lưu lượng Event Bus:**\n\n" + "\n".join(rows), parse_mode="Markdown")

def plugins_list(message):
    rows = [f"🔌 {p.get('event_type')} → `{p.get('plugin')}` [{p.get('status')}]" for p in db.plugin_registry.find()]
    bot.send_message(message.chat.id, "🔌 **Danh sách Plugins đang đăng ký lõi:**\n\n" + "\n".join(rows) if rows else "📭 Chưa đăng ký plugin nào.", parse_mode="Markdown")

def workers_health(message):
    rows = [f"👤 {w.get('worker')} | `{w.get('status')}` | Chạy cuối: {w.get('last_seen').strftime('%H:%M:%S') if w.get('last_seen') else 'N/A'}" for w in db.health.find()]
    bot.send_message(message.chat.id, "🩺 **Tình trạng sức khỏe dàn Workers:**\n\n" + "\n".join(rows) if rows else "📭 Chưa bắt được tín hiệu liên lạc của Worker nào.", parse_mode="Markdown")

# ==========================================
# 🚀 8. LUỒNG KÍCH HOẠT KÉP (WEB + BOT)
# ==========================================
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 ĐANG KHỞI ĐỘNG HỆ THỐNG KÉP (WEB + BOT)...")
    print("=" * 50)
    
    # Kích hoạt máy chủ Web giả ở luồng phụ (không chặn luồng chính)
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    print("✅ Web Server ngụy trang đã chạy ngầm.")
    
    # Kích hoạt Bot Telegram ở luồng chính
    print("✅ Telegram Polling đang kết nối...")
    # skip_pending=True xóa sạch các lệnh lỗi cũ khi bot vừa khởi động lại
    bot.infinity_polling(skip_pending=True)
        
