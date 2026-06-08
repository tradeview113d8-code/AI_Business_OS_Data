import os
from pathlib import Path
from dotenv import load_dotenv

# Tìm đường dẫn gốc của dự án
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT_DIR / '.env')

def get_env_escaped(key: str, default: str = "") -> str:
    """Đọc biến môi trường và xử lý escape ký tự đặc biệt (#, v.v.) bảo vệ chuỗi kết nối"""
    val = os.getenv(key, default)
    if val:
        try:
            # Giải quyết BUG 0.2: Tránh lỗi cắt cụt mật khẩu có ký tự đặc biệt
            return val.encode().decode('unicode_escape').strip("'"")
        except Exception:
            return val.strip("'"")
    return default

# Khai báo các cấu hình toàn cục hệ thống
MASTER_KEY = get_env_escaped('MASTER_KEY', 'default_master_key')
MONGODB_URI = get_env_escaped('MONGODB_URI', 'mongodb://localhost:27017/?replicaSet=rs0')
REDIS_URL = get_env_escaped('REDIS_URL', 'redis://localhost:6379')
TELEGRAM_BOT_TOKEN = get_env_escaped('TELEGRAM_BOT_TOKEN', '')
CHROMA_PATH = get_env_escaped('CHROMA_PATH', '/var/lib/chroma_data')
PLAYWRIGHT_BROWSERS_PATH = get_env_escaped('PLAYWRIGHT_BROWSERS_PATH', '/var/lib/playwright')

# Đảm bảo các thư mục vật lý tồn tại trên OS
os.makedirs('/var/lib/ai_business_os/temp/', exist_ok=True)
os.makedirs(CHROMA_PATH, exist_ok=True)
