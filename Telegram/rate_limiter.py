import time
from Core.redis_client import redis_client

class TelegramRateLimiter:
    """
    Bộ lọc Fixed-Window ngăn chặn tấn công từ chối dịch vụ hoặc spam click nút bấm.
    Triệt tiêu hoàn toàn rủi ro double-click tạo trùng lặp lệnh giao dịch/Transaction.
    """
    def __init__(self, limit: int = 5, window: int = 2):
        self.limit = limit     # Số lệnh tối đa được bấm
        self.window = window   # Trong chu kỳ cửa sổ thời gian (giây)

    def is_spammer(self, chat_id: int, action_key: str = "global") -> bool:
        """Trả về True nếu Giám đốc đang click chuột quá tốc độ cho phép"""
        key = f"rate_limit:{chat_id}:{action_key}"
        
        # Tăng chỉ số đếm hành vi nguyên tử trên Redis
        current_requests = redis_client.incr(key)
        
        if current_requests == 1:
            # Thiết lập khóa thời gian hết hạn cho cửa sổ bảo vệ
            redis_client.expire(key, self.window)
            return False
            
        if current_requests > self.limit:
            print(f"⚠️ [RATE_LIMIT] Chặn đứng hành vi spam nút từ Chat ID: {chat_id} tại hành động: {action_key}")
            return True
            
        return False
