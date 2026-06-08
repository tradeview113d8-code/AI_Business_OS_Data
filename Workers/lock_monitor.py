import time
from datetime import datetime, timezone
from Core.base_worker import BaseWorker
from Core.redis_client import redis_client
from Core.mongo import db

class LockMonitor(BaseWorker):
    """
    Daemon quét và giải phóng các khóa treo (Stale Locks) trên Redis.
    Nếu một Worker bị chết đột ngột mà chưa kịp xóa Lock, Lock Monitor sẽ đối chiếu
    với tín hiệu Heartbeat. Nếu Heartbeat của Worker đó đã tắt, khóa sẽ bị bẻ gãy lập tức.
    """
    def __init__(self):
        super().__init__("lock_monitor")
        
    def check_and_clear_stale_locks(self):
        print("🔍 [LOCK_MONITOR] Đang rà soát toàn bộ các khóa hệ thống...")
        
        # Lấy tất cả các key dạng project_lock trên Redis
        keys = redis_client.keys("project_lock:*")
        for key in keys:
            instance_id = redis_client.get(key)
            if not instance_id:
                continue
                
            # Trích xuất tên worker từ instance_id (Cấu trúc: name_pid_timestamp)
            worker_name = instance_id.split("_")[0] if "_" in instance_id else None
            if worker_name:
                # Kiểm tra xem Heartbeat của Worker đó còn sống không
                heartbeat = redis_client.get(f"worker_heartbeat:{worker_name}")
                if not heartbeat:
                    print(f"🚨 [LOCK_MONITOR] Phát hiện Khóa Treo tại key: {key} từ Instance đã chết ({instance_id}). Đang giải phóng...")
                    redis_client.delete(key)
                    
                    # Log tai nạn vào sos_queue để T0 hiển thị lên dashboard cho Giám đốc
                    db.sos_queue.insert_one({
                        "worker_name": self.name,
                        "error_message": f"Stale lock detected and cleared for key {key}. Worker {worker_name} was dead.",
                        "status": "resolved",
                        "created_at": datetime.now(timezone.utc)
                    })

    def run_cron_loop(self):
        print("🤖 Lock Monitor đã khởi động. Chu kỳ quét: 60 giây.")
        while True:
            try:
                self.check_and_clear_stale_locks()
            except Exception as e:
                print(f"❌ [LOCK_MONITOR] Lỗi chu kỳ: {e}")
            time.sleep(60)

if __name__ == "__main__":
    monitor = LockMonitor()
    monitor.run_cron_loop()
