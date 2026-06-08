import os
from chromadb import PersistentClient
from Core.config import CHROMA_PATH

# Bảo vệ dữ liệu Vector: Ép buộc ChromaDB khởi tạo Persistent Client 
# ghi trực tiếp xuống đĩa cứng thay vì chạy lưu trữ tạm trên RAM
chroma_client = PersistentClient(path=CHROMA_PATH)
