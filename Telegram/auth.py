from Core.config import ADMIN_IDS

def is_admin(telegram_id):
    return telegram_id in ADMIN_IDS
