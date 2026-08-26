"""CLKG 上传服务包装层 — 文件安全、验证、批次生命周期。

不修改 preingest_validator 核心规则，只在其上做上传场景适配：
- 文件安全（大小、扩展名、SHA-256、路径穿越）
- 区域一致性预检
- 调用 validate_workbook()
- 报告生成与批次状态管理
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

# 确保能导入 02_data_collection 下的 preingest_validator
_02_data_collection = Path(__file__).resolve().parent.parent / "02_data_collection"
if str(_02_data_collection) not in sys.path:
    sys.path.insert(0, str(_02_data_collection))

import openpyxl
import preingest_validator
from ingest.collection_schema import ALL_SHEETS, EXTENSION_SHEETS, SHEETS_BY_NAME, VOCAB, ColumnRole

# ───────────────────────────────────────────────────────────────────────────
# 配置
# ───────────────────────────────────────────────────────────────────────────

DEFAULT_UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "02_data_collection" / "upload_queue"
MAX_UPLOAD_MB = int(os.environ.get("CLKG_MAX_UPLOAD_MB", "25"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

ALLOWED_REGIONS = ["mustang", "qiaopi", "xinjiang", "kashgar", "liangzhu"]
ALLOWED_EXTENSIONS = {".xlsx"}
XLSX_MAGIC = b"PK\x03\x04"  # ZIP file magic


class UploadConfig:
    def __init__(self, upload_root: Path, max_bytes: int = MAX_UPLOAD_BYTES):
        self.upload_root = upload_root
        self.max_bytes = max_bytes

    @property
    def incoming_dir(self) -> Path:
        return self.upload_root / "incoming"

    @property
    def pending_dir(self) -> Path:
        return self.upload_root / "pending"

    @property
    def rejected_dir(self) -> Path:
        return self.upload_root / "rejected"

    @property
    def archive_dir(self) -> Path:
        return self.upload_root / "archive"

    @property
    def reports_dir(self) -> Path:
        return self.upload_root / "reports"


def get_config() -> UploadConfig:
    root = Path(os.environ.get("CLKG_UPLOAD_ROOT", str(DEFAULT_UPLOAD_ROOT)))
    return UploadConfig(upload_root=root)


# ───────────────────────────────────────────────────────────────────────────
# 文件安全
# ───────────────────────────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    """清理文件名，防止路径穿越。"""
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^\w\-.一-龥]", "_", name)
    return name[:200]  # 限制长度


def check_extension(filename: str) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的文件类型 '{ext}'，仅接受 .xlsx")


def check_magic(path: Path) -> None:
    with open(path, "rb") as f:
        magic = f.read(4)
    if magic != XLSX_MAGIC:
        raise ValueError("文件头不是有效的 XLSX (ZIP) 格式")


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def save_upload_stream(file_obj, dest: Path, max_bytes: int) -> int:
    """分块保存上传文件，同时强制大小限制。"""
    size = 0
    with open(dest, "wb") as f:
        while True:
            chunk = file_obj.read(8192)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                dest.unlink(missing_ok=True)
                raise ValueError(f"文件超过大小限制 ({max_bytes // 1024 // 1024} MB)")
            f.write(chunk)
    return size


# ───────────────────────────────────────────────────────────────────────────
# 模板预检
# ───────────────────────────────────────────────────────────────────────────

def precheck_template(xlsx_path: Path, declared_region: str) -> dict:
    """预检模板：识别 sheet、检查 region 一致性。

    Returns:
        {"ok": bool, "sheets_found": [...], "region_mismatches": [...], "error": str|None}
    """
    result = {"ok": False, "sheets_found": [], "region_mismatches": [], "error": None}
    try:
        wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    except Exception as ex:
        result["error"] = f"无法打开工作簿: {ex}"
        return result

    target_sheets = [sd for sd in ALL_SHEETS + EXTENSION_SHEETS if sd.sheet_name in wb.sheetnames]
    result["sheets_found"] = [sd.sheet_name for sd in target_sheets]

    if not target_sheets:
        result["error"] = "未识别到任何 CLKG 采集 sheet"
        wb.close()
        return result

    # 检查每个 sheet 的 region 列
    for sd in target_sheets:
        ws = wb[sd.sheet_name]
        region_cols = [c for c in sd.columns if c.role == ColumnRole.REGION]
        if not region_cols:
            continue
        col_idx = region_cols[0].index
        for row_idx in range(2, ws.max_row + 1):
            # 跳过示例行
            if preingest_validator._is_example_row(ws, row_idx, sd):
                continue
            cell_val = preingest_validator._clean(ws.cell(row=row_idx, column=col_idx).value)
            if cell_val is None:
                continue
            # region 可能在词表中有别名，直接比较
            if cell_val.lower() != declared_region.lower():
                result["region_mismatches"].append({
                    "sheet": sd.sheet_name,
                    "row": row_idx,
                    "expected": declared_region,
                    "found": cell_val,
                })

    wb.close()
    if result["region_mismatches"]:
        result["error"] = f"发现 {len(result['region_mismatches'])} 处区域不一致"
        return result

    result["ok"] = True
    return result


# ───────────────────────────────────────────────────────────────────────────
# 验证与报告
# ───────────────────────────────────────────────────────────────────────────

def find_authority_path(region: str) -> Optional[Path]:
    """按区域查找权威清单。"""
    candidates = [
        _02_data_collection / f"权威清单_{region}.csv",
        _02_data_collection / f"权威清单_{region}.xlsx",
        _02_data_collection / "权威实体清单.xlsx",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def run_validation(xlsx_path: Path, region: str, batch_id: str, config: UploadConfig) -> dict:
    """运行 preingest_validator，返回验证结果摘要。"""
    authority_path = find_authority_path(region)

    # 在线程池中运行验证（openpyxl 是 CPU 密集型）
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(
            preingest_validator.validate_workbook,
            xlsx_path,
            authority_path=authority_path,
        )
        report = future.result()

    # 生成报告文件（含 batch_id，避免覆盖）
    report_dir = config.reports_dir / batch_id
    report_dir.mkdir(parents=True, exist_ok=True)

    base = report_dir / f"{xlsx_path.stem}-preingest-{date.today().isoformat()}"

    md_path = base.with_suffix(".md")
    md_path.write_text(preingest_validator.render_markdown(report), encoding="utf-8")

    json_path = base.with_suffix(".json")
    json_path.write_text(preingest_validator.render_json(report), encoding="utf-8")

    # 清理报告中的临时绝对路径
    for p in (md_path, json_path):
        text = p.read_text(encoding="utf-8")
        text = text.replace(str(xlsx_path.resolve()), batch_id)
        p.write_text(text, encoding="utf-8")

    return {
        "pass": report.summary.get("pass", False),
        "error_count": report.summary.get("total_errors", 0),
        "warning_count": report.summary.get("total_warnings", 0),
        "m1_vocab_distinct_total": report.m1_vocab_distinct_total,
        "m2_out_of_vocab_bad": report.m2_out_of_vocab_bad,
        "m2_out_of_vocab_total": report.m2_out_of_vocab_total,
        "m2_rate_pct": report.m2_rate_pct,
        "m3_source_complete_bad": report.m3_source_complete_bad,
        "m4_natural_key_conflicts": report.m4_natural_key_conflicts,
        "report_json_path": str(json_path),
        "report_markdown_path": str(md_path),
        "sheets": [
            {
                "sheet_name": s.sheet_name,
                "n_rows_scanned": s.n_rows_scanned,
                "n_entities": s.n_entities,
                "n_errors": s.n_errors,
                "n_warnings": s.n_warnings,
                "issues": [
                    {
                        "row": i.row, "column": i.column, "severity": i.severity,
                        "code": i.code, "message": i.message,
                    }
                    for i in s.issues[:100]  # 只返回前 100 条
                ],
            }
            for s in report.sheets
        ],
    }


# ───────────────────────────────────────────────────────────────────────────
# 批次生命周期
# ───────────────────────────────────────────────────────────────────────────

def generate_batch_id() -> str:
    return f"upl_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _strip_batch_prefix(filename: str, batch_id: str) -> str:
    """去掉 incoming 文件名中的 batch_id 前缀，恢复原始文件名。"""
    prefix = f"{batch_id}_"
    if filename.startswith(prefix):
        return filename[len(prefix):]
    return filename


def move_to_pending(xlsx_path: Path, region: str, batch_id: str, config: UploadConfig) -> Path:
    dest_dir = config.pending_dir / region / batch_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / _strip_batch_prefix(xlsx_path.name, batch_id)
    shutil.move(str(xlsx_path), str(dest))
    return dest


def move_to_rejected(xlsx_path: Path, batch_id: str, config: UploadConfig) -> Path:
    dest_dir = config.rejected_dir / batch_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / _strip_batch_prefix(xlsx_path.name, batch_id)
    shutil.move(str(xlsx_path), str(dest))
    return dest


def move_to_archive(xlsx_path: Path, batch_id: str, config: UploadConfig) -> Path:
    dest_dir = config.archive_dir / batch_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / _strip_batch_prefix(xlsx_path.name, batch_id)
    shutil.move(str(xlsx_path), str(dest))
    return dest
