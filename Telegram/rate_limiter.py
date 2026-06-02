import time

# Bộ nhớ tạm (In-memory) lưu thời gian gửi lệnh cuối cùng của mỗi user
_user_last_request = {}

# Cấu hình thời gian tối thiểu giữa 2 lần bấm nút (giây)
RATE_LIMIT_SECONDS = 1.0 

def rate_limit(user_id: int) -> bool:
    """
    Trả về True nếu user_id được phép gọi lệnh.
    Trả về False nếu user_id đang spam quá nhanh.
    """
    current_time = time.time()
    last_request_time = _user_last_request.get(user_id, 0)
    
    # Nếu khoảng cách giữa 2 lần bấm nhỏ hơn quy định -> Chặn
    if current_time - last_request_time < RATE_LIMIT_SECONDS:
        return False
        
    # Cập nhật lại thời gian bấm nút mới nhất
    _user_last_request[user_id] = current_time
    return True
