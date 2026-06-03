import os
import sys
import threading
import json
from pathlib import Path
from datetime import datetime
from flask import Flask

# Đảm bảo đường dẫn tuyệt đối cho hệ thống Render
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Tích hợp Core logic V5
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
# 🤖 2. KHỞI TẠO BOT
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
    bot.send_message(
            message.chat.id, 
            "🛠 **Khu vực giám sát & Điều phối kỹ thuật:**", 
            reply_markup=get_admin_inline_menu(),
            parse_mode="Markdown"
        )

# Lắng nghe và điều hướng các nút bấm Inline của khu vực Admin
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
        
    # Xóa biểu tượng xoay tròn loading trên nút bấm Telegram sau khi tương tác xong
    bot.answer_callback_query(call.id)

# ==========================================
# 📥 LUỒNG NHẬP LIỆU Ý TƯỞNG VÀ SÁNG KIẾN
# ==========================================

@bot.message_handler(commands=["idea"])
def idea(message):
    if not check_permission(message): return
    msg = bot.reply_to(message, "📝 Nhập Yêu cầu / Ý tưởng thô mới của sếp:")
    bot.register_next_step_handler(msg, save_request)

def save_request(message):
    prompt_text = message.text.strip() if message.text else ""
    
    # Chốt chặn nếu nhấn nút khác thay vì gõ text
    if prompt_text in ["💡 Thêm Ý Tưởng", "🚀 Triển Khai (Deploy)", "📊 Thống Kê", "📑 Xem Báo Cáo", "🔑 Nạp API Key", "⚙️ Menu Quản Trị (Admin)"]:
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

# ==========================================
# 🔑 LUỒNG NẠP API KEY VÀ CẤU HÌNH (V5.1 SAFE)
# ==========================================

def ask_key_name(message):
    msg = bot.reply_to(message, "🎯 **Bước 1:** Nhập TÊN GỢI NHỚ cho API Key (Ví dụ: `Gemini_Free_01`, `Groq_Chính`):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, ask_key_value)

def ask_key_value(message):
    key_name = message.text.strip() if message.text else ""
    
    # BẢO VỆ CẤU TRÚC LUỒNG: Nếu bấm nút khác, thoát ngay lập tức không để đơ bot
    if key_name.startswith("/") or key_name in ["💡 Thêm Ý Tưởng", "🚀 Triển Khai (Deploy)", "📊 Thống Kê", "📑 Xem Báo Cáo", "🔑 Nạp API Key", "⚙️ Menu Quản Trị (Admin)"]:
        bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
        handle_main_menu(message)
        return

    msg = bot.reply_to(message, f"🔑 **Bước 2:** Hãy dán chuỗi **API Key thô** của nguồn `{key_name}` vào đây:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, save_raw_key_handler, key_name)

def save_raw_key_handler(message, key_name):
    raw_key = message.text.strip() if message.text else ""
    
    if not raw_key or raw_key in ["💡 Thêm Ý Tưởng", "🚀 Triển Khai (Deploy)", "📊 Thống Kê", "📑 Xem Báo Cáo", "🔑 Nạp API Key", "⚙️ Menu Quản Trị (Admin)"]:
        bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
        bot.reply_to(message, "❌ Đã hủy bỏ quy trình nạp Key do dữ liệu không hợp lệ.")
        return

    # Lưu trữ vào ngăn chứa thô api_keys_raw
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

# ==========================================
# 📊 CÁC HÀM TRUY VẤN VÀ THỰC THI (CORE FUNCTIONS)
# ==========================================

def deploy_job(message):
    """Tạo tác vụ Deploy trực tiếp vào MongoDB giống hệt ảnh mẫu của sếp"""
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
  - Chờ xử lý (Pending): `{s['pending']}`
  - Đang chạy (Processing): `{s['processing']}`
  - Hoàn thành (Completed): `{s['completed']}`
  - Bị lỗi kẹt (Dead): `{s['dead']}`

🔸 **Trục Sự kiện (Event Bus):**
  - Sự kiện chờ xử lý: `{e_pending}`
  - Sự kiện lỗi (Dead): `{e_dead}`""", parse_mode="Markdown")

def report(message):
    r = db.reports.find_one(sort=[("created_at", -1)])
    if not r:
        bot.send_message(message.chat.id, "📭 Hệ thống chưa có bản báo cáo tri thức nào được xuất bản.")
        return
    content = r.get("content", "")
    bot.send_message(message.chat.id, content[-3500:] if len(content) > 3500 else content)

# Các hàm bổ trợ đọc sâu dữ liệu trong kho MongoDB hiển thị cho Admin
def jobs_list(message):
    rows = [f"• `{j['_id']}` | {j['type']} | `{j['status']}`" 
            for j in db.jobs.find().sort("created_at", -1).limit(10)]
    bot.send_message(message.chat.id, "📋 **10 Tác vụ gần nhất trong Database:**\n\n" + "\n".join(rows) if rows else "📭 Không có Jobs nào.", parse_mode="Markdown")

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
    rows = [f"🔌 {p['event_type']} → `{p['plugin']}` [{p['status']}]" for p in db.plugin_registry.find()]
    bot.send_message(message.chat.id, "🔌 **Danh sách Plugins đang đăng ký lõi:**\n\n" + "\n".join(rows) if rows else "📭 Chưa đăng ký plugin nào.", parse_mode="Markdown")

def workers_health(message):
    rows = [f"👤 {w['worker']} | `状态: {w['status']}` | Chạy cuối: {w['last_seen'].strftime('%H:%M:%S') if w.get('last_seen') else 'N/A'}" for w in db.health.find()]
    bot.send_message(message.chat.id, "🩺 **Tình trạng sức khỏe dàn Workers:**\n\n" + "\n".join(rows) if rows else "📭 Chưa bắt được tín hiệu liên lạc của Worker nào.", parse_mode="Markdown")

# ==========================================
# 🚀 KÍCH HOẠT TIẾN TRÌNH LUỒNG (RUN)
# ==========================================

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Telegram Commander V5 Menu Interactive - RUNNING")
    print("=" * 50)
    # skip_pending=True giúp bot bỏ qua những tin nhắn cũ bị dồn ứ trong lúc ngắt kết nối
    bot.infinity_polling(skip_pending=True)
        
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
