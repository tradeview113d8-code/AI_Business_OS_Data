import threading
import time
import os
from Core.base_worker import BaseWorker
from Core.redis_client import redis_client

class EventWorker(BaseWorker):
    """
    Hệ thống tiến trình ngầm Daemon có khả năng tự động gửi tín hiệu sống (Heartbeat Thread) 
    lên Redis mỗi 5 giây, độc lập hoàn toàn với vòng lặp chính khi gọi mô hình AI bị treo mạng.
    """
    def __init__(self, name: str):
        super().__init__(name)
        self.shutdown_requested = False
        self.instance_id = f"{self.name}_{os.getpid()}_{int(time.time())}"
        
    def start_heartbeat(self):
        """Khởi chạy Thread báo tử ngầm"""
        heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        print(f"💚 [HEARTBEAT] Đã kích hoạt Thread tuần tra độc lập cho {self.instance_id}")

    def _heartbeat_loop(self):
        """Vòng lặp gửi nhịp đập lên bộ nhớ tạm Redis"""
        while not self.shutdown_requested:
            try:
                # Đăng ký khóa sống có thời gian hết hạn (TTL 15 giây) cứu hộ khi VPS chết đột ngột
                redis_client.set(f"worker_heartbeat:{self.name}", self.instance_id, ex=15)
            except Exception as e:
                print(f"⚠️ [HEARTBEAT] Lỗi ghi tín hiệu nhịp tim lên Redis: {e}")
            time.sleep(5)

    def stop(self):
        """Cờ ngắt tiến trình an toàn chủ động (Graceful Shutdown Flag)"""
        print(f"🛑 [SHUTDOWN] Đang kích hoạt quy trình dọn dẹp hạ tầng cho {self.name}...")
        self.shutdown_requested = True
