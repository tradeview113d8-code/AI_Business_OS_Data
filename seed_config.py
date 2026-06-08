import os
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
mongo_uri = os.getenv('MONGODB_URI', 'mongodb://127.0.0.1:27017/?replicaSet=rs0')

def seed_system_data():
    print("🌱 [SEED] Đang nạp dữ liệu hạt giống hệ thống...")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client.business_os_v6

    now = datetime.now(timezone.utc)

    # 1. Nạp cấu hình Admin tối cao (Dùng upsert=True chống trùng lặp)
    # Giám đốc thay đổi telegram_id thật của mình tại đây hoặc nạp qua DB sau
    admin_id = 123456789  
    db.system_admins.update_one(
        {"telegram_id": admin_id},
        {"$set": {
            "name": "Nguyen Tien Hien",
            "role": "SuperAdmin",
            "status": "active",
            "created_at": now
        }},
        upsert=True
    )
    print(f"✅ [SEED] Đã cấu hình tài khoản hạt giống Admin ID: {admin_id}")

    # 2. Cấu hình hệ thống mặc định (System Limits & Thresholds)
    db.system_config.update_one(
        {"config_key": "global_limits"},
        {"$set": {
            "max_daily_budget": 5.0,        # Giới hạn 5$ một ngày cho môi trường test
            "alert_threshold_points": 70,   # Ngưỡng rủi ro đẩy SOS
            "updated_at": now
        }},
        upsert=True
    )

    # 3. Nạp sẵn Dự án mồi (Mock Project) để test luồng E2E lập tức
    db.raw_products.update_one(
        {"project_id": "mock-project-id-v6-7"},
        {"$set": {
            "project_name": "He Dieu Hanh AI Cho Doanh Nghiep",
            "raw_input": "He thong tu dong quet insight tu sach vo, thiet lap chien luoc marketing tu dong va tu tuong tac tren mang xa hoi de ban hang.",
            "status": "active",
            "model_assignment": "gpt-3.5-turbo",
            "paused_by_user": False,
            "created_at": now
        }},
        upsert=True
    )
    
    # Kích hoạt sẵn hạn mức ví điện tử ảo cho dự án mồi trên MongoDB
    db.project_budgets.update_one(
        {"project_id": "mock-project-id-v6-7"},
        {"$set": {
            "allocated_budget": 2.0,
            "spent_budget": 0.0,
            "updated_at": now
        }},
        upsert=True
    )
    print("✅ [SEED] Đã khởi tạo dự án mồi 'mock-project-id-v6-7' và ví ngân sách $2.0 thành công.")
    print("🎉 [SEED] Quy trình nạp dữ liệu hạt giống kết thúc mỹ mãn!")

if __name__ == "__main__":
    seed_system_data()
