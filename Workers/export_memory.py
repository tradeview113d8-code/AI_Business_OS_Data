import os
import requests
from pathlib import Path

# --- CẤU HÌNH ---
# Giám đốc điền ID của Gist (chuỗi ký tự trong URL của Gist) và Tên file vào đây
GIST_ID = "https://gist.githubusercontent.com/tradeview113d8-code/c17fd2e68c12d1742522b86808bbe45d/raw/199020d099d750c9e702077303fa8c0656f8557c" 
FILENAME = "repo_memory.txt"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Các thư mục / file không cần thiết cho AI đọc
IGNORE_DIRS = [".git", "__pycache__", "venv", ".idea"]
ALLOWED_EXTENSIONS = [".py", ".yml", ".md", ".json"]
ROOT_DIR = Path(__file__).resolve().parent.parent

def generate_memory():
    memory = "# BỘ NHỚ KIẾN TRÚC HỆ ĐIỀU HÀNH AI V5\n\n"
    
    for root, dirs, files in os.walk(ROOT_DIR):
        # Bỏ qua các thư mục rác
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in ALLOWED_EXTENSIONS:
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, ROOT_DIR)
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    memory += f"\n\n{'='*50}\n"
                    memory += f"FILE: {rel_path}\n"
                    memory += f"{'='*50}\n```\n{content}\n```\n"
                except Exception as e:
                    print(f"Bỏ qua {rel_path}: {e}")
                    
    return memory

def update_gist(content):
    if not GITHUB_TOKEN:
        print("❌ Lỗi: Không tìm thấy GITHUB_TOKEN.")
        return

    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "files": {
            FILENAME: {
                "content": content
            }
        }
    }

    print(f"🚀 Đang bơm dữ liệu ({len(content)} bytes) lên Gist...")
    response = requests.patch(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        print("✅ Thành công! Gist đã được cập nhật bản mới nhất.")
        # In ra đường link Raw bất tử để Giám đốc copy cho LLM
        username = response.json().get('owner', {}).get('login', 'user')
        print(f"👉 Link cho LLM: https://gist.githubusercontent.com/{username}/{GIST_ID}/raw/{FILENAME}")
    else:
        print(f"❌ Thất bại: {response.status_code} - {response.text}")

if __name__ == "__main__":
    memory_content = generate_memory()
    update_gist(memory_content)

