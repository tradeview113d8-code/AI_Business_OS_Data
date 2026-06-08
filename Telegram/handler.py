import json
from datetime import datetime, timezone
import telebot
from telebot import types
from Telegram.bot import bot
from Telegram.auth import TelegramAuth
from Telegram.rate_limiter import TelegramRateLimiter
from Core.mongo import db
from Core.redis_client import redis_client

# Khởi tạo các module vệ tinh bảo an
auth_provider = TelegramAuth()
rate_limiter = TelegramRateLimiter(limit=6, window=2)

def escape_markdown(text: str) -> str:
    """Hàm vá lỗi và escape cấu trúc ký tự đặc biệt của Markdown V2"""
    if not text:
        return ""
    reserved_chars = r"_*[]()~`>#+-=|{}.!"
    return "".join([f"\\{c}" if c in reserved_chars else c for c in text])

def get_user_mode(chat_id: int) -> str:
    """Kiểm tra xem người dùng đang dùng chế độ Compact hay Full"""
    mode = redis_client.get(f"user_mode:{chat_id}")
    return mode.decode('utf-8') if mode else "full"

def build_common_keyboard(back_callback: str = "menu_main") -> types.InlineKeyboardMarkup:
    """Xây dựng hàng điều hướng cố định phía dưới cùng theo chuẩn UI/UX v10.1"""
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("« Quay lại", callback_data=back_callback),
        types.InlineKeyboardButton("🏠 Home", callback_data="menu_main")
    )
    return markup

# ==========================================
# LỆNH ĐIỀU KHIỂN TOÀN CỤC (GLOBAL COMMANDS)
# ==========================================
@bot.message_handler(commands=['start', 'menu'])
def cmd_start(message):
    if not auth_provider.is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Truy cập bị từ chối! Chứng chỉ Telegram của bạn không có quyền Admin tối cao.")
        return
        
    chat_id = message.chat.id
    # Gia hạn session 30 phút trên Redis
    redis_client.set(f"user_session:{chat_id}", "active", ex=1800)
    
    # Đếm số dự án đang chạy thực tế
    active_count = db.raw_products.count_documents({"status": "active"})
    pending_strategy = db.strategy_reports.count_documents({"status": "pending_approval"})
    
    is_compact = get_user_mode(chat_id) == "compact"
    
    if is_compact:
        text = f"📍 Trạm: Trung tâm Điều khiển\nProjects Active: {active_count} | Pending Strategy: {pending_strategy}"
    else:
        text = (
            f"📍 *Trạm: Bảng Điều Khiển Trung Tâm*\n\n"
            f"📊 *Hệ thống Vận hành:*\n"
            f"• Số dự án đang hoạt động: `{active_count}`\n"
            f"• Chiến lược đang chờ duyệt: `{pending_strategy}`\n\n"
            f"Chào mừng Giám đốc trở lại phòng điều hành chỉ huy Tổng lực."
        )
        
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("📁 Quản lý Dự Án", callback_data="menu_projects"))
    markup.row(types.InlineKeyboardButton("⚖️ Duyệt Chiến Lược Đang Chờ", callback_data="menu_approvals"))
    markup.row(
        types.InlineKeyboardButton("⚡ Compact Mode" if not is_compact else "📱 Full Mode", callback_data="toggle_compact"),
        types.InlineKeyboardButton("🚨 Trục Xuất Khóa Treo", callback_data="action_flush_locks")
    )
    
    bot.send_message(chat_id, escape_markdown(text), parse_mode="MarkdownV2", reply_markup=markup)

@bot.message_handler(commands=['compact'])
def cmd_compact(message):
    chat_id = message.chat.id
    current_mode = get_user_mode(chat_id)
    new_mode = "full" if current_mode == "compact" else "compact"
    redis_client.set(f"user_mode:{chat_id}", new_mode)
    bot.reply_to(message, f"🔄 Đã chuyển đổi giao diện sang chế độ: {new_mode.upper()}")

# ==========================================
# TRÌNH ĐIỀU KHIỂN NÚT BẤM (CALLBACK HANDLERS)
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    
    # 1. Lá chắn bảo mật Admin & Chống Spam click
    if not auth_provider.is_admin(user_id):
        bot.answer_callback_query(call.id, "❌ Lỗi: Quyền lực không đủ!", show_alert=True)
        return
    if rate_limiter.is_spammer(chat_id, call.data):
        bot.answer_callback_query(call.id, "⚠️ Từ từ Sếp ơi! Thao tác quá nhanh, hệ thống đang xử lý dòng tiền...", show_alert=True)
        return
        
    # Gia hạn thời gian sống session hoạt động
    redis_client.set(f"user_session:{chat_id}", "active", ex=1800)
    
    data = call.data
    is_compact = get_user_mode(chat_id) == "compact"
    
    try:
        # MENU QUAY VỀ TRANH CHỦ
        if data == "menu_main":
            bot.delete_message(chat_id, call.message.message_id)
            cmd_start(call.message)
            
        # CHUYỂN ĐỔI CHẾ ĐỘ HIỂN THỊ
        elif data == "toggle_compact":
            current_mode = get_user_mode(chat_id)
            redis_client.set(f"user_mode:{chat_id}", "full" if current_mode == "compact" else "compact")
            bot.delete_message(chat_id, call.message.message_id)
            cmd_start(call.message)

        # HÀNH ĐỘNG DỌN KHÓA KHẨN CẤP
        elif data == "action_flush_locks":
            keys = redis_client.keys("project_lock:*")
            for k in keys:
                redis_client.delete(k)
            bot.answer_callback_query(call.id, f"🚨 Đã đập tan {len(keys)} khóa treo!", show_alert=True)
            bot.delete_message(chat_id, call.message.message_id)
            cmd_start(call.message)

        # MENU DANH SÁCH DỰ ÁN
        elif data == "menu_projects":
            projects = list(db.raw_products.find().sort("created_at", -1).limit(5))
            text = "📍 *Danh sách Dự án Gần đây:*" if not is_compact else "📍 Projects:"
            
            markup = types.InlineKeyboardMarkup()
            for p in projects:
                status_emoji = "🟢" if p.get("status") == "active" else "🟡"
                markup.row(types.InlineKeyboardButton(f"{status_emoji} {p.get('project_name')}", callback_data=f"view_project:{p.get('project_id')}"))
                
            markup.row(types.InlineKeyboardButton("« Quay lại", callback_data="menu_main"))
            bot.edit_message_text(escape_markdown(text), chat_id, call.message.message_id, parse_mode="MarkdownV2", reply_markup=markup)

        # MENU DUYỆT CHIẾN LƯỢC ĐANG CHỜ PENDING
        elif data == "menu_approvals":
            # Bọc lỗi an toàn tuyệt đối Giai đoạn 1: Chỉ đọc strategy_reports
            pending_list = list(db.strategy_reports.find({"status": "pending_approval"}).limit(5))
            
            if not pending_list:
                bot.answer_callback_query(call.id, "🎉 Không có chiến lược nào đang xếp hàng chờ duyệt!", show_alert=True)
                return
                
            text = "⚖️ *Danh sách Chiến lược Chờ Duyệt:*\nChọn dự án để thẩm định chuyên sâu:"
            markup = types.InlineKeyboardMarkup()
            for report in pending_list:
                markup.row(types.InlineKeyboardButton(f"📋 Duyệt: {report.get('project_name')}", callback_data=f"review_strat:{report.get('project_id')}"))
                
            markup.row(types.InlineKeyboardButton("« Quay lại", callback_data="menu_main"))
            bot.edit_message_text(escape_markdown(text), chat_id, call.message.message_id, parse_mode="MarkdownV2", reply_markup=markup)

        # CHI TIẾT THẨM ĐỊNH CHIẾN LƯỢC
        elif data.startswith("review_strat:"):
            project_id = data.split(":")[1]
            report = db.strategy_reports.find_one({"project_id": project_id})
            
            if not report:
                bot.answer_callback_query(call.id, "❌ Không tìm thấy báo cáo chiến lược này!", show_alert=True)
                return
                
            s_data = report.get("strategy_data", {})
            insights = "\n".join([f"• {i}" for i in s_data.get("insights", [])[:3]])
            # Cắt ngắn chuỗi hiển thị tối đa 500 ký tự (Truncate Log) để bảo vệ màn hình chat
            if len(insights) > 500:
                insights = insights[:497] + "..."
                
            text = (
                f"📍 *Thẩm định Chiến lược: {report.get('project_name')}*\n\n"
                f"🧠 *Tóm tắt Insight sơ bộ:*\n{insights}\n\n"
                f"Giám đốc có phê duyệt kích nổ Tầng 3 kích hoạt chiến dịch quảng cáo không?"
            )
            
            # Thiết lập khóa ngữ cảnh tạm thời thời hạn 30 phút trên Redis
            redis_client.set(f"approval_ctx:{chat_id}:{call.message.message_id}", project_id, ex=1800)
            
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("✅ PHÊ DUYỆT", callback_data=f"approve_confirm:{project_id}"),
                types.InlineKeyboardButton("❌ BÁC BỎ", callback_data=f"approve_reject:{project_id}")
            )
            markup.row(types.InlineKeyboardButton("« Quay lại", callback_data="menu_approvals"))
            bot.edit_message_text(escape_markdown(text), chat_id, call.message.message_id, parse_mode="MarkdownV2", reply_markup=markup)

        # XỬ LÝ KHÓA TRANSACTION PHÊ DUYỆT CHÍNH THỨC
        elif data.startswith("approve_confirm:"):
            project_id = data.split(":")[1]
            lock_key = f"project_lock:{project_id}:telegram_approval"
            
            # Chiếm dụng khóa Per-project Lock tránh xung đột đa tiến trình
            if not redis_client.set(lock_key, "bot_node", ex=30, nx=True):
                bot.answer_callback_query(call.id, "⏳ Dự án đang được khóa xử lý bởi luồng khác. Thử lại sau!", show_alert=True)
                return
                
            try:
                now = datetime.now(timezone.utc)
                # Kích hoạt Chu trình Giao dịch Nguyên tử (Atomicity Transaction) bảo vệ MongoDB
                with db.client.start_session() as session:
                    with session.start_transaction():
                        # Update trạng thái report thành active
                        res = db.strategy_reports.update_one(
                            {"project_id": project_id, "status": "pending_approval"},
                            {"$set": {"status": "active", "approved_at": now}},
                            session=session
                        )
                        
                        if res.matched_count > 0:
                            # Bắn duy nhất Event chuyển giao kích hoạt
                            db.outbox_events.insert_one({
                                "event_type": "STRATEGY_APPROVED",
                                "publisher": "telegram_bot",
                                "payload": {"project_id": project_id, "approved_at": now.isoformat()},
                                "status": "pending",
                                "retry_count": 0,
                                "created_at": now,
                                "next_retry_at": now,
                                "claim_timeout": 300
                            }, session=session)
                            
                            bot.answer_callback_query(call.id, "🎉 Đã duyệt! Chiến lược chính thức kích nổ.", show_alert=True)
                        else:
                            bot.answer_callback_query(call.id, "⚠️ Thao tác thất bại. Trạng thái chiến lược đã bị thay đổi trước đó.", show_alert=True)
            finally:
                # Giải phóng khóa độc quyền
                redis_client.delete(lock_key)
                
            bot.delete_message(chat_id, call.message.message_id)
            cmd_start(call.message)

    except Exception as e:
        print(f"🚨 [HANDLER_CRASH] Tai nạn xử lý sự kiện: {e}")
        bot.answer_callback_query(call.id, f"❌ Lỗi hệ thống: {str(e)}", show_alert=True)
