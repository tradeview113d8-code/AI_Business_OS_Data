from Core.mongo import db
from Core.job_queue import queue_stats

def handle_stats(bot, message):
    try:
        s = queue_stats()
        bot.send_message(message.chat.id, f"📊 Pending: {s.get('pending',0)} | Processing: {s.get('processing',0)} | Done: {s.get('completed',0)}")
    except:
        bot.send_message(message.chat.id, "📊 Dữ liệu đang bảo trì.")

def handle_report(bot, message):
    r = db.reports.find_one(sort=[("created_at", -1)])
    if r: bot.send_message(message.chat.id, str(r.get("content", ""))[-3500:])
    else: bot.send_message(message.chat.id, "📭 Không có báo cáo nào.")
