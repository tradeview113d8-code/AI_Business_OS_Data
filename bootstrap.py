import os
from pymongo import MongoClient, IndexModel, ASCENDING, DESCENDING
from dotenv import load_dotenv

# Load env variables safely
load_dotenv()
mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/?replicaSet=rs0')

print("🔄 Đang kết nối tới MongoDB...")
client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
db = client.business_os_v6

def init_db():
    try:
        client.admin.command('ping')
        print("✅ MongoDB đang chạy!")
    except Exception as e:
        print(f"❌ Lỗi kết nối MongoDB. Đảm bảo Docker đã chạy. Chi tiết: {e}")
        return

    print("🛠️ Bắt đầu khởi tạo Indexes (Giai đoạn 1)...")

    # 1. OUTBOX EVENTS (Compound index cho Consumer Daemon)
    db.outbox_events.create_indexes([
        IndexModel([("status", ASCENDING), ("next_retry_at", ASCENDING)])
    ])

    # 2. RAW PRODUCTS (Tối ưu truy vấn T0)
    db.raw_products.create_indexes([
        IndexModel([("status", ASCENDING)]),
        IndexModel([("created_at", DESCENDING)])
    ])

    # 3. STRATEGY REPORTS (Giai đoạn 1 chỉ có cái này)
    db.strategy_reports.create_indexes([
        IndexModel([("project_id", ASCENDING)]),
        IndexModel([("status", ASCENDING)])
    ])

    # 4. TTL cho Budget Reservations (120s)
    db.budget_reservations.create_indexes([
        IndexModel([("created_at", ASCENDING)], expireAfterSeconds=120)
    ])

    # 5. TTL cho User Sessions (T0) - Redis xử lý chính, đây là backup
    db.user_sessions.create_indexes([
        IndexModel([("updated_at", ASCENDING)], expireAfterSeconds=1800)
    ])

    # 6. SOS QUEUE (Phân trang cursor-based)
    db.sos_queue.create_indexes([
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)])
    ])

    print("✅ Khởi tạo Database hoàn tất! (Tuân thủ tuyệt đối GĐ1)")

if __name__ == "__main__":
    init_db()
