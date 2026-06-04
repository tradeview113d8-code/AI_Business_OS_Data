# FILE: scripts/export_memory.py
#!/usr/bin/env python3
"""
Repo Memory Generator - Architecture-Centric Memory cho LLM
Tự động phân tích repo và sinh ra tài liệu kiến trúc + source code quan trọng
"""

import os
import re
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple
import requests

# ==================== CẤU HÌNH ====================
GIST_ID = "c17fd2e68c12d1742522b86808bbe45d"
FILENAME = "repo_memory.txt"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
ROOT_DIR = Path(__file__).resolve().parent.parent

IGNORE_DIRS = {".git", "__pycache__", "venv", ".idea", "node_modules", "dist", "build"}
ALLOWED_EXTENSIONS = {".py", ".yml", ".yaml", ".md", ".json", ".txt", ".env.example"}
# File quan trọng ưu tiên đưa source code
CRITICAL_FILES_PATTERNS = [
    "bootstrap.py", "main.py", "app.py", "run.py",
    "plugin_runner.py", "event_bus.py", "queue_manager.py",
    "mongo.py", "redis_client.py", "rabbitmq_client.py",
    "worker.py", "base_worker.py", "plugin_registry.py",
    "dead_letter_queue.py", "health.py", "metrics.py"
]

# ==================== PHÂN TÍCH TĨNH ====================
def analyze_architecture() -> Dict:
    """Phân tích kiến trúc tổng thể dựa trên file và import"""
    arch = {
        "entry_points": [],
        "databases": set(),
        "queues": set(),
        "message_brokers": set(),
        "cache": set(),
        "plugin_mechanism": "Unknown",
        "health_check": "Unknown",
        "deployment": "GitHub Actions",
        "worker_model": "Unknown"
    }
    
    # Tìm entry point
    for candidate in ["bootstrap.py", "main.py", "run.py", "app.py", "start.py"]:
        if (ROOT_DIR / candidate).exists():
            arch["entry_points"].append(candidate)
    
    # Quét import để phát hiện thư viện
    for py_file in ROOT_DIR.rglob("*.py"):
        if any(ign in py_file.parts for ign in IGNORE_DIRS):
            continue
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        if "pymongo" in content or "MongoClient" in content:
            arch["databases"].add("MongoDB")
        if "redis" in content and ("Redis(" in content or "from redis import"):
            arch["cache"].add("Redis")
            arch["message_brokers"].add("Redis (Pub/Sub)")
        if "pika" in content or "rabbitmq" in content.lower():
            arch["message_brokers"].add("RabbitMQ")
        if "queue" in content and ("insert_one" in content or "find_one_and_delete" in content):
            arch["queues"].add("MongoDB Queue")
        if "PluginRegistry" in content or "register_plugin" in content:
            arch["plugin_mechanism"] = "Manual Registration"
        if "importlib" in content and "exec" in content:
            arch["plugin_mechanism"] = "Dynamic Loading"
        if "health" in content and ("/health" in content or "health_check" in content):
            arch["health_check"] = "HTTP Endpoint / MongoDB"
        if "multiprocessing" in content or "Process(" in content:
            arch["worker_model"] = "Process-based"
        elif "threading" in content:
            arch["worker_model"] = "Thread-based"
    
    return {k: list(v) if isinstance(v, set) else v for k, v in arch.items()}

def analyze_feature_matrix() -> Dict:
    """Đánh giá trạng thái từng tính năng"""
    features = {}
    
    # API Key encryption
    encryption_exists = False
    plaintext_found = False
    for py_file in ROOT_DIR.rglob("*.py"):
        if any(ign in py_file.parts for ign in IGNORE_DIRS):
            continue
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        if "encrypt" in content and ("API" in content or "api_key" in content):
            encryption_exists = True
        if "api_keys_raw" in content and "insert_one" in content:
            plaintext_found = True
    features["API Key Encryption"] = "YES" if encryption_exists else "NO"
    features["API Key Storage"] = "Plaintext" if plaintext_found else "Unknown"
    
    # Environment validation
    validate_func = False
    enforced = False
    for py_file in ROOT_DIR.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        if "def validate_env" in content:
            validate_func = True
        if "validate_env()" in content and ("if __name__" not in content.split("validate_env()")[0]):
            enforced = True
    features["Environment Validation - Function Exists"] = "YES" if validate_func else "NO"
    features["Environment Validation - Startup Enforcement"] = "YES" if enforced else "NO"
    
    # DLQ
    dlq_collection = False
    retry = False
    redrive = False
    for py_file in ROOT_DIR.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        if "dead_letter_queue" in content or "dlq" in content:
            dlq_collection = True
        if "retry" in content and "dead_letter" in content:
            retry = True
        if "re_drive" in content or "replay" in content:
            redrive = True
    features["DLQ - Collection Exists"] = "YES" if dlq_collection else "NO"
    features["DLQ - Retry Mechanism"] = "YES" if retry else "NO"
    features["DLQ - Re-drive"] = "YES" if redrive else "NO"
    
    # Worker Timeout
    timeout_queue = False
    timeout_executor = False
    for py_file in ROOT_DIR.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        if "timeout" in content and "claim_job" in content:
            timeout_queue = True
        if "signal" in content and "alarm" in content:
            timeout_executor = True
    features["Worker Timeout - Queue Level"] = "YES" if timeout_queue else "NO"
    features["Worker Timeout - Executor Level"] = "YES" if timeout_executor else "NO"
    
    # Plugin System
    manual = False
    auto = False
    for py_file in ROOT_DIR.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        if "register_plugin" in content and "manual" not in content:
            manual = True
        if "plugins/" in str(py_file) and "importlib" in content:
            auto = True
    features["Plugin System - Manual Registration"] = "YES" if manual else "NO"
    features["Plugin System - Auto Discovery"] = "YES" if auto else "NO"
    
    return features

def find_verified_facts(arch: Dict, features: Dict) -> List[str]:
    """Sinh danh sách sự thật đã được xác minh"""
    facts = []
    if "MongoDB" in arch.get("databases", []):
        facts.append("MongoDB là database chính.")
    if "MongoDB Queue" in arch.get("queues", []):
        facts.append("MongoDB Queue đang được sử dụng.")
    if features.get("Plugin System - Manual Registration") == "YES":
        facts.append("Plugin được đăng ký thủ công.")
    if features.get("API Key Encryption") == "NO":
        facts.append("API Key đang lưu plaintext.")
    if features.get("DLQ - Collection Exists") == "YES":
        facts.append("DLQ collection tồn tại.")
    if features.get("DLQ - Retry Mechanism") == "NO":
        facts.append("Chưa có cơ chế retry từ DLQ.")
    if "Redis" not in arch.get("cache", []):
        facts.append("Chưa có Redis.")
    if "RabbitMQ" not in arch.get("message_brokers", []):
        facts.append("Chưa có RabbitMQ.")
    if features.get("Environment Validation - Startup Enforcement") == "NO":
        facts.append("validate_env() chưa được enforce ở startup.")
    return facts

def get_known_limitations(features: Dict, arch: Dict) -> List[str]:
    """Sinh danh sách giới hạn"""
    limits = []
    if features.get("API Key Encryption") == "NO":
        limits.append("API Key lưu plaintext, chưa có encryption-at-rest.")
    if features.get("DLQ - Retry Mechanism") == "NO":
        limits.append("Chưa có retry mechanism từ Dead Letter Queue.")
    if features.get("DLQ - Re-drive") == "NO":
        limits.append("Chưa có re-drive cho DLQ.")
    if features.get("Worker Timeout - Executor Level") == "NO":
        limits.append("Chưa có timeout cưỡng chế ở executor.")
    if features.get("Plugin System - Auto Discovery") == "NO":
        limits.append("Plugin auto-discovery chưa được implement.")
    if "Redis" not in arch.get("cache", []):
        limits.append("Chưa có Redis cache.")
    if "RabbitMQ" not in arch.get("message_brokers", []):
        limits.append("Chưa có RabbitMQ message broker.")
    if features.get("Environment Validation - Startup Enforcement") == "NO":
        limits.append("validate_env() tồn tại nhưng chưa được gọi ở startup.")
    return limits

def get_repository_state(features: Dict) -> Dict:
    """Phân loại mức độ hoàn thiện"""
    implemented = []
    partial = []
    planned = []
    
    # Dựa vào feature matrix để phân loại
    if features.get("DLQ - Collection Exists") == "YES":
        if features.get("DLQ - Retry Mechanism") == "YES" and features.get("DLQ - Re-drive") == "YES":
            implemented.append("Dead Letter Queue (full)")
        else:
            partial.append("Dead Letter Queue (chỉ có collection, thiếu retry/re-drive)")
    if features.get("Worker Timeout - Queue Level") == "YES":
        if features.get("Worker Timeout - Executor Level") == "YES":
            implemented.append("Worker Timeout")
        else:
            partial.append("Worker Timeout (chỉ queue level)")
    if features.get("API Key Encryption") == "NO":
        planned.append("API Key Encryption")
    if "Redis" not in features:
        planned.append("Redis integration")
    if "RabbitMQ" not in features:
        planned.append("RabbitMQ integration")
    if features.get("Plugin System - Auto Discovery") == "NO":
        planned.append("Auto Plugin Discovery")
    
    # Mặc định thêm các mục dựa trên sự tồn tại file
    if (ROOT_DIR / "dashboard").exists() or (ROOT_DIR / "web").exists():
        planned.append("Dashboard (UI chưa hoàn thiện)")
    
    return {"implemented": implemented, "partial": partial, "planned": planned}

def build_dependency_graph() -> str:
    """Xây dựng đồ thị phụ thuộc đơn giản bằng cách phân tích import"""
    graph = {}
    for py_file in ROOT_DIR.rglob("*.py"):
        if any(ign in py_file.parts for ign in IGNORE_DIRS):
            continue
        rel = str(py_file.relative_to(ROOT_DIR))
        imports = []
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        # Tìm import statements
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("import "):
                mod = line.split()[1].split(".")[0]
                imports.append(mod)
            elif line.startswith("from "):
                parts = line.split()
                if len(parts) > 1:
                    mod = parts[1].split(".")[0]
                    imports.append(mod)
        graph[rel] = list(set(imports))
    # Chỉ giữ các file quan trọng để tránh quá dài
    important_files = [f for f in graph if any(p in f for p in CRITICAL_FILES_PATTERNS)]
    result = "DEPENDENCY GRAPH\n"
    for f in important_files[:20]:  # giới hạn
        deps = [d for d in graph[f] if d != f]
        result += f"{f}\n  └─ imports: {', '.join(deps[:5])}\n"
    return result

def get_critical_files() -> List[Tuple[str, str]]:
    """Xác định file quan trọng và role của chúng"""
    critical = []
    for pattern in CRITICAL_FILES_PATTERNS:
        for f in ROOT_DIR.rglob(pattern):
            if any(ign in f.parts for ign in IGNORE_DIRS):
                continue
            rel = str(f.relative_to(ROOT_DIR))
            role = "UNKNOWN"
            content = f.read_text(encoding="utf-8", errors="ignore")
            if "bootstrap" in rel or "main" in rel:
                role = "ENTRYPOINT"
            elif "plugin" in rel and "runner" in rel:
                role = "ORCHESTRATOR"
            elif "event_bus" in rel:
                role = "COMMUNICATION"
            elif "queue" in rel:
                role = "QUEUE_MANAGER"
            elif "worker" in rel:
                role = "WORKER_BASE"
            priority = "HIGH" if role != "UNKNOWN" else "MEDIUM"
            critical.append((rel, role, priority))
    return critical

def get_recent_changes() -> List[str]:
    """Lấy 5 commit gần nhất (nếu có git)"""
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT_DIR), "log", "--oneline", "-n", "5"],
            capture_output=True, text=True, check=False
        )
        if result.returncode == 0 and result.stdout:
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        pass
    return ["Không thể truy cập git log"]

def collect_source_code() -> str:
    """Thu thập source code của các file quan trọng (không dump toàn bộ)"""
    source = "\n\n" + "="*70 + "\nSOURCE CODE (CRITICAL FILES ONLY)\n" + "="*70 + "\n"
    collected = set()
    for pattern in CRITICAL_FILES_PATTERNS:
        for f in ROOT_DIR.rglob(pattern):
            if any(ign in f.parts for ign in IGNORE_DIRS):
                continue
            rel = str(f.relative_to(ROOT_DIR))
            if rel in collected:
                continue
            collected.add(rel)
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                source += f"\n\n{'='*50}\nFILE: {rel}\n{'='*50}\n```\n{content}\n```\n"
            except Exception as e:
                source += f"\n[Lỗi đọc {rel}: {e}]\n"
    return source

# ==================== SINH BỘ NHỚ CHÍNH ====================
def generate_memory() -> str:
    memory = f"# BỘ NHỚ KIẾN TRÚC HỆ ĐIỀU HÀNH AI V5\n"
    memory += f"# Generated: {datetime.utcnow().isoformat()}\n\n"
    
    # 1. Architecture Summary
    arch = analyze_architecture()
    memory += "## 1. ARCHITECTURE SUMMARY\n"
    memory += f"- Entry Points: {', '.join(arch['entry_points']) if arch['entry_points'] else 'None found'}\n"
    memory += f"- Databases: {', '.join(arch['databases']) if arch['databases'] else 'None'}\n"
    memory += f"- Queues: {', '.join(arch['queues']) if arch['queues'] else 'None'}\n"
    memory += f"- Message Brokers: {', '.join(arch['message_brokers']) if arch['message_brokers'] else 'None'}\n"
    memory += f"- Cache: {', '.join(arch['cache']) if arch['cache'] else 'None'}\n"
    memory += f"- Plugin Mechanism: {arch['plugin_mechanism']}\n"
    memory += f"- Health Check: {arch['health_check']}\n"
    memory += f"- Deployment: {arch['deployment']}\n"
    memory += f"- Worker Model: {arch['worker_model']}\n\n"
    
    # 2. Feature Matrix
    features = analyze_feature_matrix()
    memory += "## 2. FEATURE MATRIX\n"
    for k, v in features.items():
        memory += f"- {k}: {v}\n"
    memory += "\n"
    
    # 3. Verified Facts
    facts = find_verified_facts(arch, features)
    memory += "## 3. VERIFIED FACTS\n"
    for fact in facts:
        memory += f"- {fact}\n"
    memory += "\n"
    
    # 4. Known Limitations
    limits = get_known_limitations(features, arch)
    memory += "## 4. KNOWN LIMITATIONS\n"
    for i, limit in enumerate(limits, 1):
        memory += f"{i}. {limit}\n"
    memory += "\n"
    
    # 5. Repository State
    state = get_repository_state(features)
    memory += "## 5. REPOSITORY STATE\n"
    memory += "### Implemented\n"
    for item in state["implemented"]:
        memory += f"✓ {item}\n"
    memory += "### Partial\n"
    for item in state["partial"]:
        memory += f"△ {item}\n"
    memory += "### Planned\n"
    for item in state["planned"]:
        memory += f"○ {item}\n"
    memory += "\n"
    
    # 6. Dependency Graph
    memory += "## 6. DEPENDENCY GRAPH\n"
    memory += build_dependency_graph()
    memory += "\n"
    
    # 7. Critical Files
    critical_files = get_critical_files()
    memory += "## 7. CRITICAL FILES\n"
    for rel, role, priority in critical_files:
        memory += f"- **{rel}** | Role: {role} | Priority: {priority}\n"
    memory += "\n"
    
    # 8. Recent Changes (từ git)
    recent = get_recent_changes()
    memory += "## 8. RECENT CHANGES (last 5 commits)\n"
    for commit in recent:
        memory += f"- {commit}\n"
    memory += "\n"
    
    # 9. Source Code (chỉ file quan trọng)
    memory += collect_source_code()
    
    return memory

def update_gist(content: str):
    if not GITHUB_TOKEN:
        print("❌ Lỗi: Không tìm thấy GITHUB_TOKEN.")
        return
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    payload = {"files": {FILENAME: {"content": content}}}
    print(f"🚀 Đang bơm dữ liệu ({len(content)} bytes) lên Gist...")
    resp = requests.patch(url, headers=headers, json=payload)
    if resp.status_code == 200:
        print("✅ Thành công!")
        owner = resp.json().get('owner', {}).get('login', 'user')
        print(f"👉 Link: https://gist.githubusercontent.com/{owner}/{GIST_ID}/raw/{FILENAME}")
    else:
        print(f"❌ Thất bại: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    print("🔍 Đang phân tích repository...")
    memory = generate_memory()
    update_gist(memory)
