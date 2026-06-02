"""
Ví dụ Plugin — repo vệ tinh copy file này về.

Bước 1: Copy file này vào repo mới
Bước 2: Implement handle()
Bước 3: Đăng ký vào plugin_runner.py
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from Core.plugin_registry import BasePlugin
from Core.logger import log_event


class ExamplePlugin(BasePlugin):
    """
    Plugin mẫu — lắng nghe KNOWLEDGE_READY.
    Thay handle() bằng logic thật của repo bạn.
    """
    def handle(self, event):
        knowledge_id = event["payload"].get("knowledge_id")
        k_type       = event["payload"].get("type")
        log_event("example_plugin", "INFO",
                  f"received knowledge_id={knowledge_id} type={k_type}")
        # TODO: xử lý logic thật ở đây
