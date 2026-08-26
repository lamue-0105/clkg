"""CLKG 上传批次队列 — SQLite 数据模型与 CLI。

用法:
    python 05_viz/upload_queue.py init
    python 05_viz/upload_queue.py list [--status STATUS]
    python 05_viz/upload_queue.py accept <batch_id> --reviewer <用户名>
    python 05_viz/upload_queue.py reject <batch_id> --reviewer <用户名> [--note <备注>]
    python 05_viz/upload_queue.py mark-ingested <batch_id> --ingest-batch <入库批次号>
    python 05_viz/upload_queue.py mark-failed <batch_id> --note <失败原因>
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "02_data_collection" / "upload_queue" / "queue.sqlite3"


def get_db_path() -> Path:
    return Path(os.environ.get("CLKG_UPLOAD_DB", str(DEFAULT_DB_PATH)))


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS upload_batch (
            batch_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            region TEXT NOT NULL,
            uploader TEXT NOT NULL,
            created_at TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            file_size_bytes INTEGER,
            sha256 TEXT,
            template_version TEXT,
            validator_version TEXT,
            declared_regions_json TEXT,
            error_count INTEGER DEFAULT 0,
            warning_count INTEGER DEFAULT 0,
            report_json_path TEXT,
            report_markdown_path TEXT,
            reviewed_by TEXT,
            reviewed_at TEXT,
            ingest_batch_id TEXT,
            note TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS upload_event (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            actor TEXT NOT NULL,
            event_type TEXT NOT NULL,
            detail_json TEXT,
            FOREIGN KEY (batch_id) REFERENCES upload_batch(batch_id)
        )
    """)
    conn.commit()
    return conn


def add_event(conn: sqlite3.Connection, batch_id: str, actor: str, event_type: str, detail: Optional[dict] = None) -> None:
    conn.execute(
        "INSERT INTO upload_event (batch_id, created_at, actor, event_type, detail_json) VALUES (?, ?, ?, ?, ?)",
        (batch_id, utcnow(), actor, event_type, json.dumps(detail, ensure_ascii=False) if detail else None),
    )
    conn.commit()


def create_batch(
    conn: sqlite3.Connection,
    batch_id: str,
    region: str,
    uploader: str,
    original_filename: str,
    stored_filename: str,
    file_size_bytes: int,
    sha256: str,
    template_version: str = "",
    validator_version: str = "",
    declared_regions_json: str = "[]",
) -> None:
    conn.execute(
        """INSERT INTO upload_batch
           (batch_id, status, region, uploader, created_at, original_filename, stored_filename,
            file_size_bytes, sha256, template_version, validator_version, declared_regions_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (batch_id, "received", region, uploader, utcnow(), original_filename, stored_filename,
         file_size_bytes, sha256, template_version, validator_version, declared_regions_json),
    )
    add_event(conn, batch_id, uploader, "created", {"original_filename": original_filename})


def update_status(
    conn: sqlite3.Connection,
    batch_id: str,
    status: str,
    actor: str,
    error_count: Optional[int] = None,
    warning_count: Optional[int] = None,
    report_json_path: Optional[str] = None,
    report_markdown_path: Optional[str] = None,
    reviewed_by: Optional[str] = None,
    ingest_batch_id: Optional[str] = None,
    note: Optional[str] = None,
) -> None:
    updates = ["status = ?"]
    params: list = [status]
    if error_count is not None:
        updates.append("error_count = ?")
        params.append(error_count)
    if warning_count is not None:
        updates.append("warning_count = ?")
        params.append(warning_count)
    if report_json_path is not None:
        updates.append("report_json_path = ?")
        params.append(report_json_path)
    if report_markdown_path is not None:
        updates.append("report_markdown_path = ?")
        params.append(report_markdown_path)
    if reviewed_by is not None:
        updates.append("reviewed_by = ?")
        params.append(reviewed_by)
        updates.append("reviewed_at = ?")
        params.append(utcnow())
    if ingest_batch_id is not None:
        updates.append("ingest_batch_id = ?")
        params.append(ingest_batch_id)
    if note is not None:
        updates.append("note = ?")
        params.append(note)
    params.append(batch_id)
    conn.execute(f"UPDATE upload_batch SET {', '.join(updates)} WHERE batch_id = ?", params)
    add_event(conn, batch_id, actor, f"status_{status}", {
        "error_count": error_count, "warning_count": warning_count,
        "reviewed_by": reviewed_by, "ingest_batch_id": ingest_batch_id, "note": note,
    })


def list_batches(conn: sqlite3.Connection, status: Optional[str] = None) -> list[dict]:
    sql = "SELECT * FROM upload_batch"
    params: list = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    cur = conn.execute(sql, params)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_batch(conn: sqlite3.Connection, batch_id: str) -> Optional[dict]:
    cur = conn.execute("SELECT * FROM upload_batch WHERE batch_id = ?", (batch_id,))
    row = cur.fetchone()
    if not row:
        return None
    cols = [c[0] for c in cur.description]
    return dict(zip(cols, row))


def get_events(conn: sqlite3.Connection, batch_id: str) -> list[dict]:
    cur = conn.execute(
        "SELECT * FROM upload_event WHERE batch_id = ? ORDER BY created_at",
        (batch_id,),
    )
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def print_table(rows: list[dict], columns: list[str]) -> None:
    if not rows:
        print("（无记录）")
        return
    widths = {c: max(len(str(r.get(c, ""))) for r in rows) for c in columns}
    widths = {c: max(widths[c], len(c)) for c in columns}
    header = "  ".join(c.ljust(widths[c]) for c in columns)
    print(header)
    print("  ".join("-" * widths[c] for c in columns))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(widths[c]) for c in columns))


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="CLKG 上传批次队列管理")
    p.add_argument("--db", type=Path, default=None, help="SQLite 数据库路径（默认 02_data_collection/upload_queue/queue.sqlite3）")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="初始化数据库")

    lp = sub.add_parser("list", help="列出批次")
    lp.add_argument("--status", default=None, help="按状态筛选")

    ap = sub.add_parser("accept", help="接受批次（进入待入库）")
    ap.add_argument("batch_id")
    ap.add_argument("--reviewer", required=True)

    rp = sub.add_parser("reject", help="拒绝批次")
    rp.add_argument("batch_id")
    rp.add_argument("--reviewer", required=True)
    rp.add_argument("--note", default="")

    mp = sub.add_parser("mark-ingested", help="标记已入库")
    mp.add_argument("batch_id")
    mp.add_argument("--ingest-batch", required=True, help="ingest 入库批次号")

    fp = sub.add_parser("mark-failed", help="标记入库失败")
    fp.add_argument("batch_id")
    fp.add_argument("--note", required=True, help="失败原因")

    args = p.parse_args(argv)
    conn = init_db(args.db)

    if args.cmd == "init":
        print(f"数据库已初始化: {get_db_path()}")
        return 0

    if args.cmd == "list":
        rows = list_batches(conn, status=args.status)
        print_table(rows, ["batch_id", "status", "region", "uploader", "created_at", "original_filename", "error_count", "warning_count"])
        return 0

    batch = get_batch(conn, args.batch_id)
    if not batch:
        print(f"ERROR: 批次不存在: {args.batch_id}", file=sys.stderr)
        return 1

    if args.cmd == "accept":
        if batch["status"] != "pending_review":
            print(f"ERROR: 当前状态为 {batch['status']}，只有 pending_review 可接受", file=sys.stderr)
            return 1
        update_status(conn, args.batch_id, "accepted", args.reviewer, reviewed_by=args.reviewer)
        print(f"批次 {args.batch_id} 已接受，审核人: {args.reviewer}")
        return 0

    if args.cmd == "reject":
        if batch["status"] != "pending_review":
            print(f"ERROR: 当前状态为 {batch['status']}，只有 pending_review 可拒绝", file=sys.stderr)
            return 1
        update_status(conn, args.batch_id, "rejected", args.reviewer, reviewed_by=args.reviewer, note=args.note)
        print(f"批次 {args.batch_id} 已拒绝，审核人: {args.reviewer}")
        return 0

    if args.cmd == "mark-ingested":
        if batch["status"] != "accepted":
            print(f"ERROR: 当前状态为 {batch['status']}，只有 accepted 可标记入库", file=sys.stderr)
            return 1
        update_status(conn, args.batch_id, "ingested", "system", ingest_batch_id=args.ingest_batch)
        print(f"批次 {args.batch_id} 已标记入库，ingest 批次号: {args.ingest_batch}")
        return 0

    if args.cmd == "mark-failed":
        if batch["status"] != "accepted":
            print(f"ERROR: 当前状态为 {batch['status']}，只有 accepted 可标记失败", file=sys.stderr)
            return 1
        update_status(conn, args.batch_id, "accepted", "system", note=args.note)
        print(f"批次 {args.batch_id} 入库失败已记录，原因: {args.note}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
