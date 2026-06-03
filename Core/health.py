from datetime import datetime
from Core.mongo import db, ping
from Core.config import GITHUB_TOKEN, TELEGRAM_TOKEN

def heartbeat(worker_name):
    """Lưu lại thời gian hoạt động gần nhất của từng công nhân"""
    try:
        db.health.update_one(
            {"worker": worker_name},
            {"$set": {"status": "healthy", "last_seen": datetime.utcnow()}},
            upsert=True
        )
    except:
        pass

def mongo_health():
    """Kiểm tra kết nối tới cơ sở dữ liệu"""
    return "ok" if ping() else "down"

def github_health():
    """
    Kiểm tra kết nối GitHub một cách an toàn
    Dùng get_rate_limit() thay vì get_user() để tránh lỗi 403 Forbidden trên GitHub Actions
    """
    try:
        if not GITHUB_TOKEN:
            return "not_configured"
        from github import Github
        # Gọi kiểm tra giới hạn kết nối (Rate Limit) - không cần quyền riêng tư
        Github(GITHUB_TOKEN).get_rate_limit()
        return "ok"
    except Exception as e:
        print(f"[Health] GitHub Error: {e}")
        return "down"

def telegram_health():
    """Kiểm tra xem Bot Telegram đã được cấu hình chưa"""
    return "configured" if TELEGRAM_TOKEN else "not_configured"

def deep_health():
    """Tổng hợp sức khỏe của toàn bộ hệ thống"""
    status = {
        "mongo":      mongo_health(),
        "github":     github_health(),
        "telegram":   telegram_health(),
        "checked_at": datetime.utcnow()
    }
    try:
        db.system_health.insert_one(status)
    except:
        pass
    return status

