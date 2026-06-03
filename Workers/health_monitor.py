from pathlib import Path
import sys

# Đảm bảo nhận diện được thư mục Core
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datetime import datetime, timedelta
from Core.mongo import db
from Core.health import deep_health, heartbeat
from Core.logger import log_event

WORKER = "health_monitor"

def run():
    # Điểm danh: Báo cáo với hệ thống là công nhân tuần tra vẫn đang sống
    heartbeat(WORKER)
    
    cutoff = datetime.utcnow() - timedelta(minutes=30)

    # 1. Quét tìm những công nhân đã "ngủ quên" (Offline quá 30 phút)
    for w in db.health.find():
        if w.get("last_seen") and w["last_seen"] < cutoff:
            db.notifications.insert_one({
                "message":    f"⚠️ Cảnh báo: Công nhân [{w['worker']}] đã offline!",
                "sent":       False,
                "created_at": datetime.utcnow()
            })

    # 2. Kiểm tra hàng đợi công việc (Dead jobs)
    dead_jobs = db.jobs.count_documents({"status": "dead"})
    if dead_jobs >= 5:
        db.notifications.insert_one({
            "message":    f"🚨 Báo động: Đang có {dead_jobs} nhiệm vụ bị kẹt (Dead Jobs). Yêu cầu kiểm tra!",
            "sent":       False,
            "created_at": datetime.utcnow()
        })

    # 3. Kiểm tra các sự kiện bị lỗi (Dead events)
    dead_events = db.events.count_documents({"status": "dead"})
    if dead_events >= 5:
        db.notifications.insert_one({
            "message":    f"🚨 Báo động: Băng chuyền kẹt {dead_events} sự kiện (Dead Events)!",
            "sent":       False,
            "created_at": datetime.utcnow()
        })

    # 4. Kiểm tra sức khỏe sâu (Deep health) của máy chủ, database
    status = deep_health()
    for service, state in status.items():
        # Bỏ qua trường thời gian, chỉ bắt lỗi các dịch vụ bị sập
        if service != "checked_at" and state == "down":
            db.notifications.insert_one({
                "message":    f"❌ Cảnh báo hệ thống: Dịch vụ [{service.upper()}] đang báo DOWN!",
                "sent":       False,
                "created_at": datetime.utcnow()
            })

    # 5. Ghi sổ nhật ký hoàn thành ca trực
    log_event(WORKER, "INFO", "Hoàn tất phiên tuần tra sức khỏe toàn hệ thống.")

if __name__ == "__main__":
    print(f"[{datetime.utcnow()}] Khởi động {WORKER}...")
    run()
    print("✅ Hoàn thành đi tuần.")


