"""约束规则库 — CLKG 2.0 平台的规则化在线校验（简化只读版）。

每条规则对应真实存在于当前 schema / 摄取逻辑中的约束（不是虚构的示例）：
PID 格式来自 01_sql/02_pid_minter.sql 的生成模式，containsPlace 值域来自
ingest/spatial.py 的空间推理前提，几何有效性/证据关联/置信度区间是三表模型
（evidence / conceptual_entity / entity_statement）本身隐含但从未显式校验过
的约束。

`check(region)` 直接对目标区域库跑一条 SQL，返回违规对象列表——不落库、
不做批次调度，对应 PRD 里"在线校验"的最小可行版本：随查随算，而不是一套
独立的校验任务系统。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ingest import db

RULE_SET_VERSION = "2026.08.22-01"


@dataclass
class Rule:
    rule_id: str
    label: str
    category: str
    severity: str  # error | warning | info
    applies_to: str
    explanation: str
    sql: str
    columns: list[str] = field(default_factory=lambda: ["subject_id", "predicate"])

    def check(self, region: str) -> list[dict]:
        with db.connect(region) as conn, conn.cursor() as cur:
            cur.execute(self.sql)
            rows = cur.fetchall()
        return [dict(zip(self.columns, r)) for r in rows]


RULES: list[Rule] = [
    Rule(
        rule_id="rule.pid-format.v1",
        label="PID 格式规则",
        category="identifier",
        severity="error",
        applies_to="conceptual_entity",
        explanation=(
            "PID 必须匹配 clkg:{region}:{type_abbr}-{temporal}-{7位序列号} 的生成模式"
            "（见 01_sql/02_pid_minter.sql 的 mint_pid()）。不匹配说明该记录未经"
            "铸号函数生成，或被后续脚本手动改写过，破坏了 PID 的可解析性。"
        ),
        sql=r"""
            SELECT pid, entity_type FROM conceptual_entity
            WHERE pid !~ '^clkg:[a-z][a-z0-9_]*:[a-z]{2,4}-[^-]+-[0-9]{7}$'
            LIMIT 200
        """,
        columns=["subject_id", "entity_type"],
    ),
    Rule(
        rule_id="rule.required-name.v1",
        label="核心实体命名完整性规则",
        category="completeness",
        severity="warning",
        applies_to="conceptual_entity(clu, pl, ac)",
        explanation=(
            "聚合单元(clu)、地点(pl)、行动者(ac)三类实体应至少有一条 hasName 陈述，"
            "否则该实体在检索结果和关系图中只能以裸 PID 呈现，可用性差。"
        ),
        sql="""
            SELECT ce.pid, ce.entity_type FROM conceptual_entity ce
            WHERE ce.entity_type IN ('clu','pl','ac')
              AND NOT EXISTS (
                SELECT 1 FROM entity_statement es
                WHERE es.subject_id = ce.pid AND es.predicate = 'hasName'
              )
            LIMIT 200
        """,
        columns=["subject_id", "entity_type"],
    ),
    Rule(
        rule_id="rule.geometry-valid.v1",
        label="几何有效性规则",
        category="spatial",
        severity="error",
        applies_to="entity_statement.object_geometry",
        explanation=(
            "存入的几何对象必须通过 PostGIS ST_IsValid() 校验（自相交多边形、"
            "退化环等会导致后续 ST_Contains 空间推理静默返回错误结果）。"
        ),
        sql="""
            SELECT subject_id, predicate FROM entity_statement
            WHERE object_geometry IS NOT NULL AND NOT ST_IsValid(object_geometry)
            LIMIT 200
        """,
        columns=["subject_id", "predicate"],
    ),
    Rule(
        rule_id="rule.evidence-linkage.v1",
        label="陈述-证据关联规则",
        category="provenance",
        severity="warning",
        applies_to="entity_statement.evidence_id",
        explanation=(
            "研究性陈述应关联到具体的 evidence 行（来源文件/批次/推理方法），"
            "缺失证据关联的陈述无法回答\"这个事实是怎么来的\"，不满足可追溯性要求。"
        ),
        sql="""
            SELECT subject_id, predicate FROM entity_statement
            WHERE evidence_id IS NULL
            LIMIT 200
        """,
        columns=["subject_id", "predicate"],
    ),
    Rule(
        rule_id="rule.contains-place-domain.v1",
        label="containsPlace 值域约束规则",
        category="domain_range",
        severity="error",
        applies_to="entity_statement(predicate=containsPlace)",
        explanation=(
            "containsPlace 是 ingest/spatial.py 中 ST_Contains(clu.polygon, pl.point) "
            "空间推理的产物，其主体必须是文化景观单元(clu)、客体必须是原子地点(pl)。"
            "违反此约束说明推理脚本绕过了既定生成路径，或数据被后续修改污染了类型。"
        ),
        sql="""
            SELECT es.subject_id, es.object_entity_id
            FROM entity_statement es
            JOIN conceptual_entity sub ON sub.pid = es.subject_id
            LEFT JOIN conceptual_entity obj ON obj.pid = es.object_entity_id
            WHERE es.predicate = 'containsPlace'
              AND (sub.entity_type <> 'clu' OR obj.entity_type IS DISTINCT FROM 'pl')
            LIMIT 200
        """,
        columns=["subject_id", "object_entity_id"],
    ),
    Rule(
        rule_id="rule.confidence-range.v1",
        label="置信度取值区间规则",
        category="numeric",
        severity="error",
        applies_to="entity_statement.confidence",
        explanation="confidence 字段语义为 [0,1] 区间的置信度，超出区间即为写入错误。",
        sql="""
            SELECT subject_id, predicate FROM entity_statement
            WHERE confidence IS NOT NULL AND (confidence < 0 OR confidence > 1)
            LIMIT 200
        """,
        columns=["subject_id", "predicate"],
    ),
]

RULES_BY_ID = {r.rule_id: r for r in RULES}

# 已识别但本轮demo未形式化的规则类别（PRD §4 类型/时间/空间/证据/对齐/发布 六类中
# 尚未落地为可执行 SQL 的部分）——如实标注,不假装已覆盖。
PLANNED_NOT_IMPLEMENTED = [
    {"category": "temporal", "note": "时间起止逻辑与精度/原始表达一致性校验（如侨批干支↔公历换算校验）尚未规则化。"},
    {"category": "alignment", "note": "权威映射来源与人工审核状态校验，依赖外部权威资源接入（见数据与权威资源目录），尚未实现。"},
    {"category": "publication", "note": "版本组合完整性与发布阻断门禁——本原型不做真正的发布流程，故不适用。"},
]


def run_validation(region: str, severity: str = "") -> list[dict]:
    """对单个区域库跑全部规则，返回打平的 finding 列表。"""
    out: list[dict] = []
    for rule in RULES:
        if severity and rule.severity != severity:
            continue
        try:
            findings = rule.check(region)
        except Exception as ex:
            out.append({
                "rule_id": rule.rule_id, "label": rule.label, "severity": "error",
                "category": rule.category, "subject_id": None,
                "message": f"规则执行失败: {ex}",
            })
            continue
        for f in findings:
            out.append({
                "rule_id": rule.rule_id,
                "label": rule.label,
                "severity": rule.severity,
                "category": rule.category,
                "subject_id": f.get("subject_id"),
                "detail": f,
            })
    return out
