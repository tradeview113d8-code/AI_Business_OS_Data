from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from Core.mongo import db
from Core.config import TELEGRAM_TOKEN, MOCK_MODE
from Core.logger import log_event

WORKER = "notifier"

def run():
    bot    = None
    if not MOCK_MODE:
        import telebot
        bot = telebot.TeleBot(TELEGRAM_TOKEN)

    notifications = list(db.notifications.find({"sent": {"$ne": True}}))
    admins        = list(db.users.find({"role": "admin"}))
    sent          = 0

    for notif in notifications:
        for admin in admins:
            try:
                if bot:
                    bot.send_message(admin["telegram_id"], notif["message"])
                else:
                    print(f"[MOCK] -> {admin['telegram_id']}: {notif['message']}")
                sent += 1
            except Exception as e:
                log_event(WORKER, "ERROR", str(e))
        db.notifications.update_one(
            {"_id": notif["_id"]},
            {"$set": {"sent": True}}
        )

    log_event(WORKER, "INFO", f"sent {sent} notifications")

if __name__ == "__main__":
    run()
