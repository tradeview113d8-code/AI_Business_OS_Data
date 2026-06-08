import os
import time
import shutil
from datetime import datetime, timezone
from Core.base_worker import BaseWorker

class DiskSweeper(BaseWorker):
    """
    Lao công dọn dẹp dung lượng đĩa cứng vật lý.
    Xóa toàn bộ file tạm sinh ra trong quá trình cào dữ liệu hoặc xuất báo cáo
    tại thư mục /var/lib/ai_business_os/temp/ nếu file có tuổi thọ vượt quá 1 tiếng.
    Phòng vệ tuyệt đối lỗi cạn kiệt Inode đĩa cứng gây sập Linux Server.
    """
    def __init__(self):
        super().__init__("disk_sweeper")
        self.target_dir = "/var/lib/ai_business_os/temp/"

    def clean_temp_directory(self):
        print(f"🧹 [DISK_SWEEPER] Đang quét dọn mục tiêu: {self.target_dir}")
        if not os.path.exists(self.target_dir):
            return

        now_timestamp = time.time()
        one_hour_seconds = 3600 # Ranh giới thời gian an toàn 1 tiếng

        for filename in os.listdir(self.target_dir):
            file_path = os.path.join(self.target_dir, filename)
            try:
                # Kiểm tra tuổi thọ của tệp tin trên ổ cứng
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    if now_timestamp - os.path.getmtime(file_path) > one_hour_seconds:
                        os.unlink(file_path)
                        print(f"🗑️ Đã xóa file rác: {filename}")
                elif os.path.isdir(file_path):
                    if now_timestamp - os.path.getmtime(file_path) > one_hour_seconds:
                        shutil.rmtree(file_path)
                        print(f"🗑️ Đã xóa thư mục rác: {filename}")
            except Exception as e:
                print(f"⚠️ [DISK_SWEEPER] Không thể dọn dẹp {filename}: {e}")

    def run_cron_loop(self):
        print("🤖 Disk Sweeper đã khởi chạy ngầm. Chu kỳ quét dọn: 10 phút.")
        while True:
            try:
                self.clean_temp_directory()
            except Exception as e:
                print(f"❌ [DISK_SWEEPER] Lỗi chu kỳ: {e}")
            # Khóa chu kỳ 10 phút (600s) tránh lãng phí I/O ổ đĩa
            time.sleep(600)

if __name__ == "__main__":
    sweeper = DiskSweeper()
    sweeper.run_cron_loop()
