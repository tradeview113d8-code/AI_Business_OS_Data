import os
from pymongo import MongoClient
from Core.config import MONGODB_URI

# Kỷ luật kết nối Fork-safe: Thiết lập connect=False 
# để MongoClient không tự động khởi tạo luồng ngầm trước khi tiến trình con spawn
client = MongoClient(MONGODB_URI, connect=False, serverSelectionTimeoutMS=5000)

# Định danh Database duy nhất cho hệ thống V6
db = client.business_os_v6
