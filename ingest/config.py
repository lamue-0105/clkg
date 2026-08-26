"""Environment-driven configuration. Loads ~/clkg/.env if present."""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _ROOT = Path(__file__).resolve().parent.parent
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass


PG_HOST     = os.getenv("PG_HOST", "localhost")
PG_PORT     = int(os.getenv("PG_PORT", "5432"))
PG_USER     = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")
PG_DB_SUFFIX = os.getenv("PG_DB_SUFFIX", "_cl_kg")

NAS_ROOT = Path(os.getenv("NAS_ROOT", "/Volumes/clkg_data"))

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()
QWEN_MODEL        = os.getenv("QWEN_MODEL", "qwen-plus")
QWEN_BASE_URL     = os.getenv("QWEN_BASE_URL",
                              "https://dashscope.aliyuncs.com/compatible-mode/v1")

ENABLE_NER = os.getenv("ENABLE_NER", "0") == "1" and bool(DASHSCOPE_API_KEY)


def db_name(region: str) -> str:
    # Region is free-form: any new heritage project drops in without code changes.
    if not region or not region.replace("_", "").isalnum():
        raise ValueError(f"invalid region: {region!r}")
    return f"{region}{PG_DB_SUFFIX}"


def project_root(region: str) -> Path:
    return NAS_ROOT / region
