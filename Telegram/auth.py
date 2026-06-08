import os
from Core.mongo import db

class TelegramAuth:
    """
    Hệ thống phân quyền Admin tối cao bảo vệ Trạm chỉ huy T tầng 0.
    Chỉ cho phép các telegram_id được cấu hình hoặc lưu trong DB thực thi lệnh.
    """
    def __init__(self):
        # Đọc danh sách ID Admin cứng từ biến môi trường làm lá chắn vòng ngoài
        self.hardcoded_admins = [
            int(uid.strip()) 
            for uid in os.getenv("ALLOWED_TELEGRAM_IDS", "0").split(",") 
            if uid.strip().isdigit()
        ]

    def is_admin(self, telegram_id: int) -> bool:
        """Trả về True nếu user_id vượt qua bài kiểm tra bảo mật"""
        if not telegram_id:
            return False
        if telegram_id in self.hardcoded_admins:
            return True
            
        # Truy vấn kiểm tra chứng chỉ động trong bộ sưu tập admins của MongoDB
        admin_doc = db.system_admins.find_one({"telegram_id": telegram_id, "status": "active"})
        return bool(admin_doc)
