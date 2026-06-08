import os
import time
from pymongo import MongoClient, IndexModel, ASCENDING, DESCENDING
from dotenv import load_dotenv

load_dotenv()
mongo_uri = os.getenv('MONGODB_URI', 'mongodb://127.0.0.1:27017/?replicaSet=rs0')

print("🔄 Codespaces đang kích hoạt kiểm tra hạ tầng dữ liệu...")
# Chờ đợi MongoDB khởi động hoàn toàn trong container
time.sleep(3)

client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
db = client.business_os_v6

def init_codespace_db():
    try:
        # Kích hoạt khẩn cấp Replica Set trực tiếp từ bên trong môi trường
        admin_client = MongoClient('mongodb://127.0.0.1:27017/', serverSelectionTimeoutMS=5000)
        try:
            admin_client.admin.command('replSetInitiate')
            print("⚙️ [REPLICASET] Đã kích hoạt cấu hình Replica Set thành công.")
            time.sleep(2)
        except Exception as e:
            # Nếu đã cấu hình từ trước, bỏ qua lỗi bảo vệ Idempotent
            if "already initialized" not in str(e):
                print(f"⚠️ Thống kê trạng thái Replica Set: {e}")

        client.admin.command('ping')
        print("✅ Kết nối liên thông trục cơ sở dữ liệu MongoDB!")
    except Exception as e:
        print(f"❌ Lỗi hạ tầng: Môi trường Docker chưa sẵn sàng. Chi tiết: {e}")
        return

    print("🛠️ Thiết lập hệ thống Index độc quyền cho Giai đoạn 1...")
    db.outbox_events.create_indexes([IndexModel([("status", ASCENDING), ("next_retry_at", ASCENDING)])])
    db.raw_products.create_indexes([IndexModel([("status", ASCENDING)]), IndexModel([("created_at", DESCENDING)])])
    db.strategy_reports.create_indexes([IndexModel([("project_id", ASCENDING)]), IndexModel([("status", ASCENDING)])])
    db.budget_reservations.create_indexes([IndexModel([("created_at", ASCENDING)], expireAfterSeconds=120)])
    db.user_sessions.create_indexes([IndexModel([("updated_at", ASCENDING)], expireAfterSeconds=1800)])
    db.sos_queue.create_indexes([IndexModel([("status", ASCENDING), ("created_at", DESCENDING)])])
    print("🎉 MÔI TRƯỜNG CODESPACES ĐÃ SẴN SÀNG TRIỂN KHAI PHÁT TRIỂN CODE!")

if __name__ == "__main__":
    init_codespace_db()
