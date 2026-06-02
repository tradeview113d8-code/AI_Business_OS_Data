"""
Plugin Runner — entry point cho plugin system.

Thêm plugin mới:
    1. Tạo class trong Plugins/
    2. Import và register_plugin() ở đây
    3. Chạy file này
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from Core.plugin_registry import register_plugin, run_once, run_forever
from Core.event_bus import EventType

# ==========================================
# ĐĂNG KÝ PLUGINS TẠI ĐÂY
# ==========================================
from Plugins.example_plugin import ExamplePlugin
register_plugin(EventType.KNOWLEDGE_READY, ExamplePlugin)

# Thêm plugin mới:
# from Plugins.seo_plugin import SEOPlugin
# register_plugin(EventType.REPORT_WRITTEN, SEOPlugin)
# ==========================================

import sys

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "once"
    if mode == "forever":
        run_forever(interval=5)
    else:
        processed, errors = run_once()
        print(f"Done: processed={processed} errors={errors}")
