import os
import telebot
import threading
import time
import uuid
from Core.config import TELEGRAM_BOT_TOKEN
from Core.redis_client import redis_client

# Khởi tạo thực thể bot lõi từ thư viện pyTelegramBotAPI
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode=None)

# Khởi tạo chuỗi định danh duy nhất cho tiến trình khi nổ máy (Singleton Lock ID)
INSTANCE_ID = str(uuid.uuid4())
lock_key = "singleton_bot_instance_lock"

def check_singleton_lock():
    """
    Background Thread chạy song song gia hạn quyền sinh sát độc quyền mỗi 30 giây.
    Nếu phát hiện có instance thứ hai cố tình chạy đè, instance cũ sẽ tự động tự sát.
    """
    print(f"🛡️ [SINGLETON] Trạm chỉ huy khởi động với ID thực thể: {INSTANCE_ID}")
    
    while True:
        try:
            # Thử chiếm quyền sở hữu khóa độc quyền trên Redis (TTL 45 giây)
            acquired = redis_client.set(lock_key, INSTANCE_ID, ex=45, nx=True)
            
            if acquired:
                print("💚 [SINGLETON] Đăng ký độc quyền Bot thành công. Đang giữ chốt...")
            else:
                current_holder = redis_client.get(lock_key)
                if current_holder == INSTANCE_ID:
                    # Nếu chính ta đang cầm khóa, tiến hành gia hạn thời gian sống (Keep-alive)
                    redis_client.expire(lock_key, 45)
                else:
                    print(f"🚨 [SINGLETON] Phát hiện thực thể Bot mới trùng lặp ({current_holder}) đã chiếm quyền điều khiển! Tiến trình tự hủy...")
                    os._exit(0) # Ngắt khẩn cấp cấp độ hệ điều hành để tránh lặp tin nhắn
                    
        except Exception as e:
            print(f"⚠️ [SINGLETON] Lỗi tuần tra khóa độc quyền Redis: {e}")
            
        time.sleep(30)

def run_singleton_bot():
    """Kích hoạt trạm chỉ huy an toàn tuyệt đối"""
    if not TELEGRAM_BOT_TOKEN:
        print("❌ [TELEGRAM] TELEGRAM_BOT_TOKEN trống rỗng! Không thể nổ máy T0.")
        return
        
    # Khởi chạy Thread giám sát trùng lặp tiến trình
    monitor_thread = threading.Thread(target=check_singleton_lock, daemon=True)
    monitor_thread.start()
    
    print("🚀 [TELEGRAM] Bot Telegram đang bắt đầu cơ chế infinity_polling chủ động kéo data...")
    # Sử dụng infinity_polling theo Kế hoạch v10.1: Không mở port, tự phục hồi khi rớt mạng mạng nhà
    bot.infinity_polling(timeout=20, long_polling_timeout=25)

if __name__ == "__main__":
    run_singleton_bot()
