from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from Core.mongo import db
from Core.event_bus import pending_count
from Telegram.auth import is_admin

def handle_deploy(bot, message):
    job_id = db.jobs.insert_one({"type": "deploy", "status": "pending", "created_at": datetime.utcnow()}).inserted_id
    bot.reply_to(message, f"🚀 **Deploy Job ID:** `{job_id}`\nBăng chuyền cập nhật đang chạy ngầm...", parse_mode="Markdown")

def show_admin_menu(bot, message):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📋 Xem Jobs", callback_data="admin_jobs"), InlineKeyboardButton("💀 Dead Jobs", callback_data="admin_dead"))
    markup.row(InlineKeyboardButton("🚌 Event Bus", callback_data="admin_events"), InlineKeyboardButton("🔌 Plugins", callback_data="admin_plugins"))
    markup.row(InlineKeyboardButton("🩺 Sức khỏe Workers", callback_data="admin_health"))
    bot.send_message(message.chat.id, "🛠 **Trạm kiểm soát:**", reply_markup=markup, parse_mode="Markdown")

def register_admin_callbacks(bot):
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
    def handle_admin_callbacks(call):
        if not is_admin(call.from_user.id): return
        
        a = call.data
        if a == "admin_jobs":
            rows = [f"`{j['_id']}` | {j.get('type','N/A')} | {j.get('status','N/A')}" for j in db.jobs.find().sort("created_at", -1).limit(10)]
            bot.send_message(call.message.chat.id, "📋 Jobs:\n" + "\n".join(rows) if rows else "📭 Trống", parse_mode="Markdown")
        elif a == "admin_dead":
            rows = [f"❌ `{d.get('job_id')}` - {str(d.get('error'))[:40]}" for d in db.dead_letter_queue.find().sort("failed_at", -1).limit(5)]
            bot.send_message(call.message.chat.id, "💀 Dead Jobs:\n" + "\n".join(rows) if rows else "✅ Trống", parse_mode="Markdown")
        elif a == "admin_events":
            rows = [f"`{et}`: {pending_count(et)} pending" for et in ["request_received", "analysis_done", "knowledge_ready", "report_written"]]
            bot.send_message(call.message.chat.id, "🚌 Event Bus:\n" + "\n".join(rows), parse_mode="Markdown")
        elif a == "admin_health":
            rows = [f"👤 {w.get('worker')} | {w.get('status')}" for w in db.health.find()]
            bot.send_message(call.message.chat.id, "🩺 Workers:\n" + "\n".join(rows) if rows else "📭 Trống", parse_mode="Markdown")
        
        bot.answer_callback_query(call.id)
                    
