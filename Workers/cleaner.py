from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datetime import datetime, timedelta
from Core.mongo import db
from Core.health import heartbeat
from Core.logger import log_event

WORKER = "cleaner"

def run():
    # Điểm danh sự sống
    heartbeat(WORKER)
    
    # Mốc thời gian: Bất cứ thứ gì kẹt quá 15 phút đều bị coi là có vấn đề
    stuck_time = datetime.utcnow() - timedelta(minutes=15)
    
    # Quét băng chuyền Sự kiện (Events)
    stuck_events = db.events.find({
        "status": {"$in": ["pending", "processing"]},
        "updated_at": {"$lt": stuck_time}
    })
    
    rescued_count = 0
    dead_count = 0

    for event in stuck_events:
        retries = event.get("retries", 0)
        
        if retries < 3:
            # Cấp cứu: Trả lại trạng thái pending để làm lại
            db.events.update_one(
                {"_id": event["_id"]},
                {
                    "$set": {"status": "pending", "updated_at": datetime.utcnow()},
                    "$inc": {"retries": 1}
                }
            )
            log_event(WORKER, "WARNING", f"🔄 Đã hô hấp nhân tạo sự kiện {event.get('type')} (Lần {retries + 1})")
            rescued_count += 1
        else:
            # Vô phương cứu chữa: Đẩy vào góc (Dead status)
            db.events.update_one(
                {"_id": event["_id"]},
                {"$set": {"status": "dead", "updated_at": datetime.utcnow()}}
            )
            log_event(WORKER, "ERROR", f"💀 Sự kiện {event.get('type')} đã chết hẳn sau 3 lần cấp cứu.")
            dead_count += 1

    if rescued_count > 0 or dead_count > 0:
        print(f"[{datetime.utcnow()}] Y tá dọn dẹp: Hồi sinh {rescued_count} ca, Chuyển nhà xác {dead_count} ca.")
    else:
        print(f"[{datetime.utcnow()}] Băng chuyền sạch sẽ, không có ca kẹt.")

if __name__ == "__main__":
    run()
    
