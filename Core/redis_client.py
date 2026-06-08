import redis
import json
import time
from bson import ObjectId
from datetime import datetime
from Core.config import REDIS_URL

class CustomJSONEncoder(json.JSONEncoder):
    """Bộ mã hóa JSON tùy chỉnh nhằm giải quyết triệt để lỗi Serialize dữ liệu phức tạp"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

class CustomJSONDecoder(json.JSONDecoder):
    """Bộ giải mã hỗ trợ khôi phục các chuỗi dạng ISO Datetime"""
    def __init__(self, *args, **kwargs):
        super().__init__(object_hook=self.dict_to_object, *args, **kwargs)

    def dict_to_object(self, d):
        for k, v in d.items():
            if isinstance(v, str):
                try:
                    d[k] = datetime.fromisoformat(v)
                except ValueError:
                    pass
        return d

print("🔄 Đang thiết lập kết nối Redis với cơ chế Exponential Backoff...")
# Cấu hình cơ chế thử lại tự động khi khởi động dịch vụ nóng nhằm chống sập race condition
redis_client = redis.Redis.from_url(
    REDIS_URL, 
    decode_responses=True,
    retry_on_timeout=True,
    socket_timeout=5,
    socket_connect_timeout=5
)

def safe_redis_execute(func, *args, **kwargs):
    """Hàm bọc thực thi lệnh Redis an toàn tuyệt đối với 5 lần thử lại"""
    retries = 5
    delay = 2
    for i in range(retries):
        try:
            return func(*args, **kwargs)
        except (redis.ConnectionError, redis.TimeoutError) as e:
            if i == retries - 1:
                raise e
            print(f"⚠️ Thất bại kết nối Redis. Đang thử lại sau {delay} giây... (Lần {i+1}/{retries})")
            time.sleep(delay)
            delay *= 2
