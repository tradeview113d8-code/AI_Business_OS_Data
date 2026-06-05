#!/usr/bin/env python3
"""
export_memory.py

Architecture-centric Repo Memory Generator
Principles:
- FACT > INFERENCE > UNKNOWN
- Never mark YES without evidence
- Separate verified facts from assumptions
- Environment-driven configuration
"""

import os
from pathlib import Path
from datetime import datetime
import requests

ROOT_DIR = Path(__file__).resolve().parent.parent

GIST_ID = os.getenv("GIST_ID")
GIST_FILENAME = os.getenv("GIST_FILENAME", "repo_memory.txt")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "venv",
    ".idea",
    "node_modules",
    "dist",
    "build",
}

# Thêm bộ lọc đuôi file để tránh đọc nhầm file ảnh, video hay file thực thi
ALLOWED_EXTENSIONS = {".py", ".yml", ".yaml", ".md", ".json", ".txt"}

def validate_env():
    if not GIST_ID:
        raise RuntimeError("Missing GIST_ID environment variable")

    if os.getenv("REPO_MEMORY_UPLOAD_ONLY") == "1" and not GITHUB_TOKEN:
        raise RuntimeError("Missing GITHUB_TOKEN environment variable")


def iter_files():
    for path in ROOT_DIR.rglob("*"):
        if not path.is_file():
            continue

        if any(part in IGNORE_DIRS for part in path.parts):
            continue

        yield path


def generate_tree(dir_path: Path, prefix: str = "") -> list:
    """Hàm tạo sơ đồ cây thư mục trực quan"""
    lines = []
    
    try:
        # Sắp xếp: Thư mục đứng trước, file đứng sau
        paths = sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return []

    # Loại bỏ các thư mục rác
    paths = [p for p in paths if not any(ignored in p.parts for ignored in IGNORE_DIRS)]

    for i, path in enumerate(paths):
        is_last = i == len(paths) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{path.name}")
        
        if path.is_dir():
            extension = "    " if is_last else "│   "
            lines.extend(generate_tree(path, prefix + extension))
            
    return lines


def generate_memory():
    lines = []

    lines.append("# REPO MEMORY")
    lines.append(f"Generated: {datetime.utcnow().isoformat()} UTC")
    lines.append("")

    # 1. TẠO CÂY THƯ MỤC
    lines.append("## 🌳 CÂY THƯ MỤC HỆ THỐNG")
    lines.append("```text")
    lines.append(f"{ROOT_DIR.name}/")
    lines.extend(generate_tree(ROOT_DIR))
    lines.append("```")
    lines.append("")

    valid_files = list(iter_files())

    lines.append("## VERIFIED FACTS")
    lines.append(f"- Files detected: {len(valid_files)}")
    lines.append("")

    # 2. XUẤT CHI TIẾT MÃ NGUỒN TỪNG FILE
    lines.append("## 💻 CHI TIẾT MÃ NGUỒN TỪNG FILE")
    
    # Sắp xếp theo thứ tự alphabet để LLM dễ định vị
    valid_files.sort(key=lambda p: str(p).lower())
    
    for f in valid_files:
        try:
            rel = f.relative_to(ROOT_DIR)
        except Exception:
            rel = f
            
        if f.suffix not in ALLOWED_EXTENSIONS:
            continue
            
        try:
            content = f.read_text(encoding="utf-8")
            lines.append("="*50)
            lines.append(f"FILE: {rel}")
            lines.append("="*50)
            
            # Định dạng block code cho Markdown
            block_type = f.suffix[1:] if f.suffix else "text"
            if block_type == "py": block_type = "python"
            
            lines.append(f"```{block_type}")
            lines.append(content)
            lines.append("```")
            lines.append("")
        except Exception as e:
            lines.append(f"// Bỏ qua {rel}: Không thể đọc ({e})")
            lines.append("")

    return "\n".join(lines)


def write_memory_file():
    content = generate_memory()
    output = ROOT_DIR / "repo_memory.txt"
    output.write_text(content, encoding="utf-8")
    print(f"Generated: {output}")
    return output


def upload_gist(content: str):
    url = f"https://api.github.com/gists/{GIST_ID}"

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    payload = {
        "files": {
            GIST_FILENAME: {
                "content": content
            }
        }
    }

    print(f"Bơm dữ liệu lên Gist ID: {GIST_ID} ...")
    response = requests.patch(url, headers=headers, json=payload, timeout=60)

    if response.status_code != 200:
        raise RuntimeError(
            f"Gist upload failed: {response.status_code} {response.text}"
        )

    print("Gist updated successfully")


def main():
    validate_env()

    if os.getenv("REPO_MEMORY_ONLY") == "1":
        write_memory_file()
        return

    if os.getenv("REPO_MEMORY_UPLOAD_ONLY") == "1":
        path = ROOT_DIR / "repo_memory.txt"

        if not path.exists():
            raise FileNotFoundError("repo_memory.txt not found")

        upload_gist(path.read_text(encoding="utf-8"))
        return

    path = write_memory_file()
    upload_gist(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
