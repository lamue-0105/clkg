"""CLKG Explorer API — 只读演示 + 数据采集上传（认证后）。

Run from the repo root so the `ingest` package resolves:
    cd ~/clkg && python3 05_viz/run.py

(uvicorn can't import a module starting with a digit directly, so launch via
run.py in this same folder instead — see that file for the actual entrypoint.)
"""
from __future__ import annotations

import csv
import importlib.util
import io
import json
import os
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from ingest import db, ontology
import catalog
import rules

# ───────────────────────────────────────────────────────────────────────────
# dynamic imports for sibling modules (05_viz is not a valid package name)
# ───────────────────────────────────────────────────────────────────────────

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


upload_queue = _load_module("upload_queue", HERE / "upload_queue.py")
upload_service = _load_module("upload_service", HERE / "upload_service.py")

app = FastAPI(title="CLKG Explorer API")

# 同源部署后移除宽松 CORS；仅允许同源请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],  # 同源部署不需要 CORS；空列表禁止跨域
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=True,
)

REGIONS = ["mustang", "qiaopi", "xinjiang", "kashgar", "liangzhu"]
REGION_LABELS = {
    "mustang": "木斯塘 · 文化景观",
    "qiaopi": "侨批 · 文献/记忆遗产",
    "xinjiang": "新疆 · 考古遗产",
    "kashgar": "喀什 · 考古遗产(新疆子项目)",
    "liangzhu": "良渚 · 考古遗产",
}


def _region_or_404(region: str) -> str:
    if region not in REGIONS:
        raise HTTPException(404, f"unknown region '{region}'")
    return region


# ───────────────────────────────────────────────────────────────────────────
# authentication (collector / reviewer)
# ───────────────────────────────────────────────────────────────────────────

security = HTTPBasic()

COLLECTOR_USER = os.environ.get("CLKG_COLLECTOR_USER", "")
COLLECTOR_PASSWORD = os.environ.get("CLKG_COLLECTOR_PASSWORD", "")
REVIEWER_USER = os.environ.get("CLKG_REVIEWER_USER", "")
REVIEWER_PASSWORD = os.environ.get("CLKG_REVIEWER_PASSWORD", "")

if not COLLECTOR_USER or not COLLECTOR_PASSWORD:
    raise RuntimeError("CLKG_COLLECTOR_USER 和 CLKG_COLLECTOR_PASSWORD 环境变量必须设置")
if not REVIEWER_USER or not REVIEWER_PASSWORD:
    raise RuntimeError("CLKG_REVIEWER_USER 和 CLKG_REVIEWER_PASSWORD 环境变量必须设置")


class Principal:
    def __init__(self, username: str, role: Literal["collector", "reviewer"]):
        self.username = username
        self.role = role


def verify_auth(credentials: HTTPBasicCredentials = Depends(security)) -> Principal:
    """HTTP Basic Auth — 返回带角色的 Principal。"""
    # collector
    if secrets.compare_digest(credentials.username, COLLECTOR_USER) and \
       secrets.compare_digest(credentials.password, COLLECTOR_PASSWORD):
        return Principal(username=credentials.username, role="collector")
    # reviewer
    if secrets.compare_digest(credentials.username, REVIEWER_USER) and \
       secrets.compare_digest(credentials.password, REVIEWER_PASSWORD):
        return Principal(username=credentials.username, role="reviewer")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="用户名或密码错误",
        headers={"WWW-Authenticate": "Basic"},
    )


def verify_reviewer(principal: Principal = Depends(verify_auth)) -> Principal:
    """仅 reviewer 可访问。"""
    if principal.role != "reviewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要 reviewer 权限",
        )
    return principal


# ───────────────────────────────────────────────────────────────────────────
# upload endpoints
# ───────────────────────────────────────────────────────────────────────────

PUBLIC_DIR = HERE / "public"


@app.get("/upload.html")
def upload_page(principal: Principal = Depends(verify_auth)):
    """认证后的上传页面（优先于 StaticFiles）。"""
    return FileResponse(PUBLIC_DIR / "upload.html")


@app.get("/api/upload/regions")
def upload_regions(principal: Principal = Depends(verify_auth)):
    return {"regions": upload_service.ALLOWED_REGIONS, "labels": REGION_LABELS}


@app.get("/api/upload/template")
def upload_template(principal: Principal = Depends(verify_auth)):
    template_path = REPO_ROOT / "02_data_collection" / "CLKG_采集模板.xlsx"
    if not template_path.exists():
        raise HTTPException(404, "模板文件不存在")
    return FileResponse(template_path, filename="CLKG_采集模板.xlsx")


@app.post("/api/upload")
async def upload_file(
    principal: Principal = Depends(verify_auth),
    file: UploadFile = File(...),
    region: str = Form(...),
):
    """上传并验证一个批次。"""
    import traceback
    try:
        return await _upload_file_impl(principal, file, region)
    except HTTPException:
        raise
    except Exception as ex:
        traceback.print_exc()
        raise HTTPException(500, f"上传处理内部错误: {type(ex).__name__}: {ex}")


async def _upload_file_impl(principal: Principal, file: UploadFile, region: str):
    config = upload_service.get_config()
    config.incoming_dir.mkdir(parents=True, exist_ok=True)

    # 1. region 白名单
    if region not in upload_service.ALLOWED_REGIONS:
        raise HTTPException(400, f"不支持的区域 '{region}'")

    # 2. 文件名清理与扩展名检查
    safe_name = upload_service.sanitize_filename(file.filename or "upload.xlsx")
    try:
        upload_service.check_extension(safe_name)
    except ValueError as ex:
        raise HTTPException(400, str(ex))

    # 3. 保存到 incoming（带大小限制）
    batch_id = upload_service.generate_batch_id()
    incoming_path = config.incoming_dir / f"{batch_id}_{safe_name}"
    try:
        size = upload_service.save_upload_stream(file.file, incoming_path, config.max_bytes)
        upload_service.check_magic(incoming_path)
    except ValueError as ex:
        incoming_path.unlink(missing_ok=True)
        raise HTTPException(400, str(ex))

    sha256 = upload_service.compute_sha256(incoming_path)

    # 4. 模板预检（sheet 识别 + region 一致性）
    precheck = upload_service.precheck_template(incoming_path, region)
    if not precheck["ok"]:
        incoming_path.unlink(missing_ok=True)
        raise HTTPException(400, f"模板预检失败: {precheck['error']}")

    # 5. 初始化数据库批次
    conn = upload_queue.init_db()
    upload_queue.create_batch(
        conn,
        batch_id=batch_id,
        region=region,
        uploader=principal.username,
        original_filename=safe_name,
        stored_filename=incoming_path.name,
        file_size_bytes=size,
        sha256=sha256,
        template_version="2026.08.22-01",  # TODO: 从模板或 collection_schema 读取
        validator_version=upload_service.preingest_validator.__version__ if hasattr(upload_service.preingest_validator, "__version__") else "unknown",
        declared_regions_json=json.dumps([region]),
    )
    upload_queue.update_status(conn, batch_id, "validating", principal.username)

    # 6. 运行验证
    try:
        result = upload_service.run_validation(incoming_path, region, batch_id, config)
    except Exception as ex:
        upload_queue.update_status(conn, batch_id, "validation_failed", "system", note=str(ex))
        upload_service.move_to_rejected(incoming_path, batch_id, config)
        conn.close()
        raise HTTPException(500, f"验证过程出错: {ex}")

    # 7. 根据验证结果移动文件
    if result["pass"]:
        stored_path = upload_service.move_to_pending(incoming_path, region, batch_id, config)
        upload_queue.update_status(
            conn, batch_id, "pending_review", principal.username,
            error_count=result["error_count"],
            warning_count=result["warning_count"],
            report_json_path=result["report_json_path"],
            report_markdown_path=result["report_markdown_path"],
        )
    else:
        stored_path = upload_service.move_to_rejected(incoming_path, batch_id, config)
        upload_queue.update_status(
            conn, batch_id, "validation_failed", principal.username,
            error_count=result["error_count"],
            warning_count=result["warning_count"],
            report_json_path=result["report_json_path"],
            report_markdown_path=result["report_markdown_path"],
        )

    conn.close()

    return {
        "batch_id": batch_id,
        "status": "pending_review" if result["pass"] else "validation_failed",
        "pass": result["pass"],
        "error_count": result["error_count"],
        "warning_count": result["warning_count"],
        "report_url": f"/api/upload/{batch_id}/report",
    }


@app.get("/api/upload/pending")
def upload_pending_list(principal: Principal = Depends(verify_reviewer)):
    conn = upload_queue.init_db()
    rows = upload_queue.list_batches(conn, status="pending_review")
    conn.close()
    # 清理路径
    for r in rows:
        for key in ("report_json_path", "report_markdown_path"):
            if r.get(key):
                r[key] = Path(r[key]).name
    return rows


@app.get("/api/upload/{batch_id}")
def upload_batch_detail(batch_id: str, principal: Principal = Depends(verify_auth)):
    conn = upload_queue.init_db()
    batch = upload_queue.get_batch(conn, batch_id)
    conn.close()
    if not batch:
        raise HTTPException(404, "批次不存在")
    # collector 只能看自己的批次
    if principal.role == "collector" and batch["uploader"] != principal.username:
        raise HTTPException(403, "无权查看该批次")
    # 不返回服务器绝对路径
    for key in ("report_json_path", "report_markdown_path"):
        if batch.get(key):
            batch[key] = Path(batch[key]).name
    return batch


@app.get("/api/upload/{batch_id}/report")
def upload_batch_report(batch_id: str, principal: Principal = Depends(verify_auth), format: str = "json"):
    conn = upload_queue.init_db()
    batch = upload_queue.get_batch(conn, batch_id)
    conn.close()
    if not batch:
        raise HTTPException(404, "批次不存在")
    if principal.role == "collector" and batch["uploader"] != principal.username:
        raise HTTPException(403, "无权查看该批次")

    path_str = batch.get("report_json_path") if format == "json" else batch.get("report_markdown_path")
    if not path_str:
        raise HTTPException(404, "报告不存在")
    path = Path(path_str)
    if not path.exists():
        raise HTTPException(404, "报告文件不存在")

    if format == "json":
        return json.loads(path.read_text(encoding="utf-8"))
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")


@app.get("/api/upload/{batch_id}/file")
def upload_batch_file(batch_id: str, principal: Principal = Depends(verify_reviewer)):
    conn = upload_queue.init_db()
    batch = upload_queue.get_batch(conn, batch_id)
    conn.close()
    if not batch:
        raise HTTPException(404, "批次不存在")

    config = upload_service.get_config()
    # 根据状态确定文件位置
    if batch["status"] == "pending_review":
        file_path = config.pending_dir / batch["region"] / batch_id / batch["original_filename"]
    elif batch["status"] in ("validation_failed", "rejected"):
        file_path = config.rejected_dir / batch_id / batch["original_filename"]
    elif batch["status"] in ("accepted", "ingested"):
        file_path = config.archive_dir / batch_id / batch["original_filename"]
    else:
        file_path = config.incoming_dir / batch["stored_filename"]

    if not file_path.exists():
        raise HTTPException(404, "文件不存在")
    return FileResponse(file_path, filename=batch["original_filename"])


@app.post("/api/upload/{batch_id}/review")
def upload_batch_review(
    batch_id: str,
    principal: Principal = Depends(verify_reviewer),
    action: str = Form(...),  # "accept" or "reject"
    note: str = Form(""),
):
    conn = upload_queue.init_db()
    batch = upload_queue.get_batch(conn, batch_id)
    if not batch:
        conn.close()
        raise HTTPException(404, "批次不存在")
    if batch["status"] != "pending_review":
        conn.close()
        raise HTTPException(400, f"当前状态为 {batch['status']}，只有 pending_review 可审核")

    config = upload_service.get_config()
    src = config.pending_dir / batch["region"] / batch_id / batch["original_filename"]

    if action == "accept":
        upload_service.move_to_archive(src, batch_id, config)
        upload_queue.update_status(conn, batch_id, "accepted", principal.username, reviewed_by=principal.username, note=note)
    elif action == "reject":
        upload_service.move_to_rejected(src, batch_id, config)
        upload_queue.update_status(conn, batch_id, "rejected", principal.username, reviewed_by=principal.username, note=note)
    else:
        conn.close()
        raise HTTPException(400, "action 必须是 accept 或 reject")

    conn.close()
    return {"batch_id": batch_id, "status": action + "ed", "reviewed_by": principal.username}


@app.get("/api/regions")
def regions():
    out = []
    for r in REGIONS:
        row = {"region": r, "label": REGION_LABELS[r]}
        try:
            with db.connect(r) as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT (SELECT count(*) FROM conceptual_entity),"
                    " (SELECT count(*) FROM entity_statement),"
                    " (SELECT count(*) FROM evidence)"
                )
                e, s, ev = cur.fetchone()
                row.update(entities=e, statements=s, evidence=ev)
        except Exception as ex:  # region db may be unreachable / empty
            row.update(entities=0, statements=0, evidence=0, note=str(ex)[:120])
        out.append(row)
    return out


@app.get("/api/recent")
def recent(limit: int = 40):
    """Most recently ingested evidence rows across all regions — feeds the
    '数据采集' panel: a live feed of what has landed in the databases."""
    out = []
    for r in REGIONS:
        try:
            with db.connect(r) as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, source_type, source_name, collector, recording_date
                    FROM evidence ORDER BY id DESC LIMIT %s
                    """,
                    (limit,),
                )
                for eid, stype, sname, collector, rdate in cur.fetchall():
                    out.append({
                        "region": r,
                        "region_label": REGION_LABELS[r],
                        "evidence_id": eid,
                        "source_type": stype,
                        "source_name": sname,
                        "collector": collector,
                        "recording_date": str(rdate) if rdate else None,
                    })
        except Exception:
            continue
    out.sort(key=lambda x: (x["region"], -x["evidence_id"]))
    return out[:limit]


@app.get("/api/search")
def search(
    region: str,
    q: str = "",
    entity_type: str = "",
    predicate: str = "",
    limit: int = 60,
):
    region = _region_or_404(region)
    where = ["1=1"]
    params: dict = {"limit": limit}
    if entity_type:
        where.append("ce.entity_type = %(entity_type)s")
        params["entity_type"] = entity_type
    if q:
        where.append(
            "(ce.pid ILIKE %(qlike)s OR EXISTS ("
            " SELECT 1 FROM entity_statement es2"
            " WHERE es2.subject_id = ce.pid AND es2.object_value ILIKE %(qlike)s"
            + (" AND es2.predicate = %(predicate)s" if predicate else "")
            + "))"
        )
        params["qlike"] = f"%{q}%"
        if predicate:
            params["predicate"] = predicate
    elif predicate:
        where.append(
            "EXISTS (SELECT 1 FROM entity_statement es2"
            " WHERE es2.subject_id = ce.pid AND es2.predicate = %(predicate)s)"
        )
        params["predicate"] = predicate

    sql = f"""
        SELECT ce.pid, ce.entity_type,
          (SELECT object_value FROM entity_statement
             WHERE subject_id = ce.pid AND predicate = 'hasName' LIMIT 1) AS name,
          EXISTS (SELECT 1 FROM entity_statement es3
                   WHERE es3.subject_id = ce.pid AND es3.object_geometry IS NOT NULL) AS has_geom
        FROM conceptual_entity ce
        WHERE {' AND '.join(where)}
        ORDER BY ce.pid
        LIMIT %(limit)s
    """
    with db.connect(region) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return rows


@app.get("/api/entity/{region}/{pid:path}")
def entity_detail(region: str, pid: str):
    region = _region_or_404(region)
    with db.connect(region) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT es.statement_id, es.predicate, es.object_value, es.object_entity_id,
                   ST_AsGeoJSON(es.object_geometry) AS geom,
                   es.valid_time_start, es.valid_time_end, es.confidence, es.evidence_id,
                   e.source_type, e.source_name, e.collector, e.recording_date,
                   e.description AS evidence_description
            FROM entity_statement es
            LEFT JOIN evidence e ON e.id = es.evidence_id
            WHERE es.subject_id = %s ORDER BY es.predicate, es.statement_id
            """,
            (pid,),
        )
        cols = [c.name for c in cur.description]
        stmts = [dict(zip(cols, r)) for r in cur.fetchall()]

        # resolve names of any linked entities for display
        linked_ids = {s["object_entity_id"] for s in stmts if s["object_entity_id"]}
        names = {}
        if linked_ids:
            cur.execute(
                "SELECT subject_id, object_value FROM entity_statement"
                " WHERE predicate = 'hasName' AND subject_id = ANY(%s)",
                (list(linked_ids),),
            )
            names = dict(cur.fetchall())

        cur.execute(
            "SELECT entity_type FROM conceptual_entity WHERE pid = %s", (pid,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "entity not found")
        entity_type = row[0]

    for s in stmts:
        if s["object_entity_id"]:
            s["object_name"] = names.get(s["object_entity_id"])

    for s in stmts:
        if s["evidence_id"] is not None:
            s["evidence"] = {
                "id": s["evidence_id"],
                "source_type": s.pop("source_type", None),
                "source_name": s.pop("source_name", None),
                "collector": s.pop("collector", None),
                "recording_date": str(s.pop("recording_date", None) or "") or None,
                "description": s.pop("evidence_description", None),
            }
        else:
            s.pop("source_type", None)
            s.pop("source_name", None)
            s.pop("collector", None)
            s.pop("recording_date", None)
            s.pop("evidence_description", None)
            s["evidence"] = None
        s["generation_method"] = (
            "rule_inference" if s["evidence"] and s["evidence"]["source_type"] == "spatial_inference"
            else "source_record"
        )

    return {"pid": pid, "entity_type": entity_type, "statements": stmts}


@app.get("/api/geo")
def geo(region: str, entity_type: str = "", limit: int = 3000):
    region = _region_or_404(region)
    where = ["es.object_geometry IS NOT NULL"]
    params: list = []
    if entity_type:
        where.append("ce.entity_type = %s")
        params.append(entity_type)
    params.append(limit)

    sql = f"""
        SELECT es.subject_id, ce.entity_type, ST_AsGeoJSON(es.object_geometry) AS geom,
          (SELECT object_value FROM entity_statement
             WHERE subject_id = es.subject_id AND predicate = 'hasName' LIMIT 1) AS name
        FROM entity_statement es
        JOIN conceptual_entity ce ON ce.pid = es.subject_id
        WHERE {' AND '.join(where)}
        LIMIT %s
    """
    features = []
    with db.connect(region) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        import json as _json
        for pid, etype, geom, name in cur.fetchall():
            if not geom:
                continue
            features.append({
                "type": "Feature",
                "geometry": _json.loads(geom),
                "properties": {"pid": pid, "entity_type": etype, "name": name},
            })
    return {"type": "FeatureCollection", "features": features}


# ─────────────────────────────────────────────────────────────────────────
# 2.0：版本 / CL-Onto 建模 / 规则与校验 / 数据与权威资源目录 / 专题 / 导出
# ─────────────────────────────────────────────────────────────────────────

@app.get("/api/versions")
def versions():
    return catalog.VERSION_COMBO


def _entity_counts_by_type() -> dict[str, int]:
    agg: dict[str, int] = {}
    for r in REGIONS:
        try:
            with db.connect(r) as conn, conn.cursor() as cur:
                cur.execute("SELECT entity_type, count(*) FROM conceptual_entity GROUP BY 1")
                for t, n in cur.fetchall():
                    agg[t] = agg.get(t, 0) + n
        except Exception:
            continue
    return agg


@app.get("/api/ontology/concepts")
def ontology_concepts():
    inv = ontology.inventory()
    counts = _entity_counts_by_type()
    attr_types: dict[str, set] = {}
    for p, a in inv.items():
        for t in a["subj"]:
            attr_types.setdefault(t, set()).add(p)
    out = []
    for t, (cn, czh, crm) in ontology.CLASSES.items():
        out.append({
            "type_abbr": t,
            "class_name": cn,
            "label_zh": czh,
            "cidoc_crm": f"crm:{crm}" if crm else None,
            "entity_count": counts.get(t, 0),
            "distinct_predicates": len(attr_types.get(t, set())),
        })
    return out


@app.get("/api/ontology/predicates")
def ontology_predicates():
    inv = ontology.inventory()
    zh = ontology._zh_labels()
    out = []
    for p, a in sorted(inv.items()):
        crm, level, note = ontology._crm_for(p)
        kind = "object" if a["ref"] else ("spatial" if a["geo"] else "datatype")
        out.append({
            "predicate": p,
            "label_zh": zh.get(p, ""),
            "kind": kind,
            "domain": sorted(a["subj"]),
            "range": sorted(a["objt"]) if a["ref"] else ("geometry" if a["geo"] else "literal"),
            "cidoc_crm": crm,
            "match_level": level,
            "statement_count": a["n"],
        })
    return out


@app.get("/api/ontology/crm-mapping")
def ontology_crm_mapping():
    md, csv_text = ontology.build_crm_table()
    return {"markdown": md, "csv": csv_text}


@app.get("/api/ontology/ttl")
def ontology_ttl():
    ttl = ontology.build_turtle(version=catalog.VERSION_COMBO["ontology_version"])
    return PlainTextResponse(ttl, media_type="text/turtle")


@app.get("/api/rules")
def rules_list():
    return {
        "rule_set_version": rules.RULE_SET_VERSION,
        "implemented": [
            {
                "rule_id": r.rule_id, "label": r.label, "category": r.category,
                "severity": r.severity, "applies_to": r.applies_to,
                "explanation": r.explanation,
            }
            for r in rules.RULES
        ],
        "planned_not_implemented": rules.PLANNED_NOT_IMPLEMENTED,
    }


@app.get("/api/validation")
def validation(region: str, severity: str = ""):
    region = _region_or_404(region)
    findings = rules.run_validation(region, severity=severity)
    summary: dict[str, int] = {}
    for f in findings:
        summary[f["severity"]] = summary.get(f["severity"], 0) + 1
    return {"region": region, "rule_set_version": rules.RULE_SET_VERSION,
            "summary": summary, "findings": findings}


@app.get("/api/inference")
def inference():
    out = []
    for r in REGIONS:
        try:
            with db.connect(r) as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.id, e.source_type, e.source_name, e.collector,
                           e.description, e.metadata,
                           (SELECT count(*) FROM entity_statement es
                              WHERE es.evidence_id = e.id) AS n_statements
                    FROM evidence e WHERE e.source_type = 'spatial_inference'
                    """
                )
                cols = [c.name for c in cur.description]
                for row in cur.fetchall():
                    d = dict(zip(cols, row))
                    d["region"] = r
                    d["rule_id"] = "rule.contains-place-domain.v1"
                    out.append(d)
        except Exception:
            continue
    return out


@app.get("/api/catalog/sources")
def catalog_sources():
    return catalog.SOURCES


@app.get("/api/catalog/authorities")
def catalog_authorities():
    return catalog.AUTHORITIES


@app.get("/api/topics/{topic}")
def topic_detail(topic: str):
    if topic not in catalog.TOPICS:
        raise HTTPException(404, f"unknown topic '{topic}'")
    t = dict(catalog.TOPICS[topic])
    region = t["region"]
    try:
        with db.connect(region) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT (SELECT count(*) FROM conceptual_entity),"
                " (SELECT count(*) FROM entity_statement),"
                " (SELECT count(*) FROM entity_statement WHERE predicate='containsPlace')"
            )
            entities, statements, contains_place = cur.fetchone()
            cur.execute(
                "SELECT entity_type, count(*) FROM conceptual_entity"
                " GROUP BY 1 ORDER BY 2 DESC"
            )
            by_type = cur.fetchall()
        t["live_stats"] = {
            "entities": entities, "statements": statements,
            "contains_place": contains_place,
            "by_type": [{"entity_type": x, "count": n} for x, n in by_type],
        }
    except Exception as ex:
        t["live_stats"] = {"error": str(ex)[:150]}
    try:
        findings = rules.run_validation(region)
        summary: dict[str, int] = {}
        for f in findings:
            summary[f["severity"]] = summary.get(f["severity"], 0) + 1
        t["validation_summary"] = summary
    except Exception as ex:
        t["validation_summary"] = {"error": str(ex)[:150]}
    return t


@app.get("/api/export")
def export(
    region: str,
    format: str = "json",
    entity_type: str = "",
    q: str = "",
    predicate: str = "",
    limit: int = 500,
):
    region = _region_or_404(region)
    rows = search(region=region, q=q, entity_type=entity_type, predicate=predicate, limit=limit)
    payload = {
        "data_version": catalog.VERSION_COMBO["data_version"],
        "ontology_version": catalog.VERSION_COMBO["ontology_version"],
        "rule_set_version": catalog.VERSION_COMBO["rule_set_version"],
        "authority_version": catalog.VERSION_COMBO["authority_version"],
        "region": region,
        "query": {"q": q, "entity_type": entity_type, "predicate": predicate},
        "count": len(rows),
        "results": rows,
    }
    if format == "csv":
        buf = io.StringIO()
        buf.write(
            f"# data_version={payload['data_version']} "
            f"ontology_version={payload['ontology_version']} "
            f"rule_set_version={payload['rule_set_version']}\n"
        )
        if rows:
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return Response(content=buf.getvalue(), media_type="text/csv")
    return payload


# ───────────────────────────────────────────────────────────────────────────
# static files (must be LAST — all API routes above take precedence)
# ───────────────────────────────────────────────────────────────────────────

@app.get("/{full_path:path}")
def serve_static(full_path: str):
    """Serve public/ directory; fallback for all non-API routes."""
    if ".." in full_path:
        raise HTTPException(404, "Not Found")
    file_path = PUBLIC_DIR / full_path
    if file_path.is_dir():
        file_path = file_path / "index.html"
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, "Not Found")
    return FileResponse(file_path)
