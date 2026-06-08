import os
import time
from pymongo import MongoClient, IndexModel, ASCENDING, DESCENDING
from dotenv import load_dotenv

load_dotenv()
mongo_uri = os.getenv('MONGODB_URI', 'mongodb://127.0.0.1:27017/?replicaSet=rs0')

print("🔄 [BOOTSTRAP] Hệ thống đang kiểm tra hạ tầng máy chủ ảo Codespaces...")
time.sleep(2) # Chờ cổng mạng container ổn định

client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
db = client.business_os_v6

def init_database_architecture():
    try:
        # Kích hoạt khẩn cấp cụm Replica Set nếu môi trường ảo vừa dựng trắng tinh
        admin_client = MongoClient('mongodb://127.0.0.1:27017/', serverSelectionTimeoutMS=5000)
        try:
            admin_client.admin.command('replSetInitiate')
            print("⚙️ [REPLICASET] Đã kích nổ cấu hình định danh Replica Set.")
            time.sleep(2)
        except Exception as e:
            if "already initialized" not in str(e):
                print(f"ℹ️ Trạng thái Replica Set: {e}")

        client.admin.command('ping')
        print("✅ Kết nối thông suốt trục cơ sở dữ liệu MongoDB!")
    except Exception as e:
        print(f"❌ [CRITICAL] Môi trường Docker sập hoặc cấu hình sai URI: {e}")
        return

    print("🛠️ Bắt đầu tuần tra và khởi tạo hệ thống Index độc quyền Giai đoạn 1...")
    
    # 1. OUTBOX_EVENTS INDEX COMPOUND (Phục vụ Worker quét tăng tốc xử lý)
    db.outbox_events.create_indexes([
        IndexModel([("status", ASCENDING), ("event_type", ASCENDING), ("next_retry_at", ASCENDING)], name="idx_outbox_patrol")
    ])
    
    # 2. RAW_PRODUCTS INDEX (Phục vụ truy vấn T0 hiển thị menu)
    db.raw_products.create_indexes([
        IndexModel([("status", ASCENDING)]),
        IndexModel([("created_at", DESCENDING)])
    ])
    
    # 3. STRATEGY_REPORTS INDEX (Chỉ làm bảng chiến lược theo kỷ luật v10.1)
    db.strategy_reports.create_indexes([
        IndexModel([("project_id", ASCENDING)], unique=True),
        IndexModel([("status", ASCENDING)])
    ])
    
    # 4. TTL INDEX CHO DÒNG TIỀN (Tự động xóa bản ghi đóng băng sau 120 giây)
    db.budget_reservations.create_indexes([
        IndexModel([("created_at", ASCENDING)], expireAfterSeconds=120, name="idx_budget_ttl")
    ])
    
    # 5. TTL INDEX CHO USER SECTIONS (Hết hạn sau 30 phút = 1800 giây)
    db.user_sessions.create_indexes([
        IndexModel([("updated_at", ASCENDING)], expireAfterSeconds=1800, name="idx_session_ttl")
    ])

    # 6. SOS QUEUE CURSOR INDEX (Phục vụ hiển thị cảnh báo phân trang)
    db.sos_queue.create_indexes([
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)])
    ])

    print("🎉 [BOOTSTRAP] KHỞI TẠO TOÀN BỘ CẤU TRÚC HẠ TẦNG INDEX THÀNH CÔNG VÀ CHUẨN XÁC V10.1!")

if __name__ == "__main__":
    init_database_architecture()
