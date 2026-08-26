"""Entry point for the CLKG explorer demo — works around 05_viz not being a
valid Python module name (starts with a digit) by loading api.py directly.

Usage:
    cd ~/clkg && python3 05_viz/run.py
Then open http://<IP>:8008/explorer.html in a browser.
"""
import importlib.util
import os
import sys
from pathlib import Path

import uvicorn

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(HERE))

# 环境变量检查（上传功能必须）
_REQUIRED_ENV = [
    "CLKG_COLLECTOR_USER", "CLKG_COLLECTOR_PASSWORD",
    "CLKG_REVIEWER_USER", "CLKG_REVIEWER_PASSWORD",
]
_missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
if _missing:
    print(f"WARNING: 以下环境变量未设置，上传功能将不可用: {', '.join(_missing)}", file=sys.stderr)
    print("  如需启用上传，请设置后重启。只读演示不受影响。", file=sys.stderr)

spec = importlib.util.spec_from_file_location("clkg_viz_api", HERE / "api.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

if __name__ == "__main__":
    uvicorn.run(mod.app, host="0.0.0.0", port=8008, log_level="info")
