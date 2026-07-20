"""L2 — passage → candidate CL-Onto statements.

qwen_ner.py answers "what names appear in this text". That is not enough for a
document corpus: a book asserts *relations* ("Te consists of five clusters",
"the castle dates to 1570 by dendrochronology"), and a name list throws the
relation away. This module extracts typed triples against a closed predicate
vocabulary instead, so the output drops straight into entity_statement.

Three things make document extraction different from every existing connector,
and each shows up in the design:

1. **It is interpretive.** A CSV cell is a fact; a sentence is a reading of one.
   Every candidate carries an assertion strength, and that strength — not a
   flat 1.0 — sets `confidence`. Scholarly prose is full of "the author
   suggests", "it is possible that", "local tradition holds"; flattening those
   into plain assertions would be a data-integrity failure, not a rounding
   error.

2. **Dating claims are not equal.** "1570 by dendrochronology" and "746 by
   legend" are both dates in the same book. `hasDateBasis` keeps them
   distinguishable, and drives confidence.

3. **Provenance must be per-fact.** One paragraph yields several claims of
   differing quality, so evidence is minted per fact, not per passage. Each
   evidence row carries the supporting quote and the locator, which makes the
   L4 human-verification gate a simple row-by-row review.

Entity binding is NOT done here. Candidates carry surface names; resolving
"Lo Manthang" to an existing pid is L3's job.

    facts = extract_facts(text, locator="p.116", doc_key="doc:...")
    rows  = to_statement_rows(facts, region="mustang", doc_path=p)
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import ssl
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from .. import config
from ..staging import StatementRow

log = logging.getLogger(__name__)

_CACHE_DIR = Path.home() / ".cache" / "clkg" / "doc_facts"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Bump when the prompt or schema changes so old cache entries are not reused and
# statements stay traceable to the version that produced them.
PROMPT_VERSION = "doc_facts/v4"


# ═══════════════════════════════════════════════════════════════════════════
# controlled vocabulary
# ═══════════════════════════════════════════════════════════════════════════

# Reused from the live CL-Onto predicate set. Deliberately a subset: handing the
# model all 82 datatype predicates (most of them qiaopi- or xinjiang-specific)
# is noise that invites mis-selection.
CORE_PREDICATES: dict[str, str] = {
    "hasName":              "名称 / name",
    "hasType":              "类型（寺院/民居/城堡/佛塔/聚落…）",
    "hasDescription":       "简述",
    "hasEra":               "所属时期（世纪/朝代等粗粒度）",
    "hasTimeSpan":          "起讫年代，如 '1441-1447'",
    "hasLayer":             "聚落层级标注（群体/区域/单体）",
    "hasPreservationState": "保存状态（完好/坍塌/已拆除/废墟）",
    "hasMaterial":          "主要建造材料（夯土/土坯/石/木）",
    "hasNote":              "其他值得保留的事实",
    "containsPlace":        "包含某个下级地点（clu → pl）",
    "tookPlaceIn":          "事件发生地（ev → pl/clu）",
    "carriedOutBy":         "行为施事者（ev → ac）",
}

# New for long-form documents. A book states things geometry cannot derive and
# a spreadsheet has no column for.
EXTENSION_PREDICATES: dict[str, str] = {
    "partOfUnit":       "从属于某个更大的聚落单元。文本断言的层级，"
                        "与 ST_Contains 推出的 containsPlace 是两条独立证据链。"
                        "村落联盟这类单元没有多边形，只能由文本给出。",
    "hasSubUnitCount":  "由几个下级单元组成，如 Te 由 5 个 cluster 组成",
    "hasSettlementForm": "聚落形态类型。括号内为常见取值，仅供参考，不是选择题："
                        "（崖窟/山顶设防/密集堡垒式/线型沿街/紧凑单街/低密度谷底）。"
                        "原文没有明确描述形态时必须留空，严禁从中挑一个最接近的。",
    "hasConstructionDate": "营建年代",
    "hasFoundedBy":     "创建者（人名，保留原文）",
    "hasAffiliation":   "教派归属（萨迦/宁玛/噶举/苯教…）",
    "hasPillarCount":   "柱数——藏式建筑按柱计间，是规模与地位的直接指标",
    "hasStoreyCount":   "层数",
    "hasDimension":     "尺寸，保留原文单位，如 '19 × 13.5 m'、'墙高 17 m 底厚 1.5 m'",
    "surveyedBy":       "测绘者",
    "hasSurveyYear":    "测绘年份",
}

ALL_PREDICATES = {**CORE_PREDICATES, **EXTENSION_PREDICATES}

ENTITY_TYPES: dict[str, str] = {
    "pl":  "原子地点：可单独定位的一处",
    "clu": "文化景观单元：一群同类对象或一片区域构成的聚合实体",
    "ac":  "行动者：人物 / 家族 / 机构",
    "ev":  "事件：有时间的发生（营建、拆除、废弃、重修）",
}

# The clu/pl split is the project's core concept (技术说明与实验设计手册 §3.3) and
# the first thing a general-purpose model gets wrong: v1 of the prompt typed 29
# of 32 candidates as `pl`, including every settlement in the passage. Stating
# the rule is not enough — it needs worked examples on both sides of the line.
_TYPE_RULE = """判定 clu 还是 pl（最容易错，请先判类型再抽事实）：
  一群同类对象、一片区域、一个有名字的聚居体 → clu
  可单独定位、有独立边界的一处建筑物或构筑物 → pl

  clu 的例子：村、镇、聚落、住区聚簇(cluster)、村落联盟、行政区、洞窟聚落群
  pl  的例子：一座寺院、一栋民居、一座城堡、一座佛塔、一道城墙、一座门楼

  典型错误：把村庄判成 pl。凡是「某某村/某某镇/某某聚落/某某聚簇」一律 clu。"""

# Buildings sit inside settlements, and prose moves between the two without
# repeating the subject ("Gemi 的寺院由 Tashigön 王 1512 年建"). v1 hoisted the
# monastery's construction date, the palace's rebuild date and the town wall's
# ruined state all onto the settlement Gemi.
_SUBJECT_RULE = """主语必须是该属性真正的所有者：
  文中说「某聚落的寺院建于 X 年」，主语是那座寺院，不是聚落。
  文中说「某聚落的城墙已无遗存」，主语是城墙，不是聚落。
  若原文没有给出该建筑的专名，就用「聚落名+通名」，如「Gemi 寺院」「Gemi 王宫」。
  宁可主语略粗，也不要把建筑的属性挂到包含它的聚落上。"""

# Assertion strength → confidence. The gap between `asserted` and `hypothesised`
# is the whole point: it must be wide enough that a downstream filter can act on
# it without a lookup table.
ASSERTION_CONFIDENCE: dict[str, float] = {
    "asserted":     0.90,   # 作者以事实陈述
    "reported":     0.70,   # 作者转述他人研究或地方说法
    "inferred":     0.55,   # 作者据证据推论
    "hypothesised": 0.35,   # 作者明确存疑或提问
}

# Dating evidence, strongest first. Multiplies into confidence for date claims.
DATE_BASIS: dict[str, float] = {
    "dendrochronology": 1.00,
    "radiocarbon":      1.00,
    "inscription":      0.95,
    "documentary":      0.90,
    "stylistic":        0.70,
    "tradition":        0.50,   # 地方传说
    "inference":        0.60,
    "unknown":          0.75,
}


# ═══════════════════════════════════════════════════════════════════════════
# candidate
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CandidateFact:
    """One extracted triple, not yet bound to any pid."""
    subject_name: str
    subject_type: str                 # pl | clu | ac | ev
    predicate: str
    object_value: Optional[str] = None       # literal
    object_name: Optional[str] = None        # entity reference (surface form)
    object_type: Optional[str] = None        # pl | clu | ac | ev
    assertion: str = "asserted"
    date_basis: Optional[str] = None
    quote: str = ""
    locator: str = ""
    doc_key: str = ""

    @property
    def confidence(self) -> float:
        c = ASSERTION_CONFIDENCE.get(self.assertion, 0.5)
        if self.date_basis:
            c *= DATE_BASIS.get(self.date_basis, 0.75)
        return round(c, 3)

    def natural_key(self) -> str:
        """Stable key for the subject entity, namespaced by document.

        Names are kept verbatim rather than normalised: the same settlement is
        spelled several ways across a single book (Kag / Kagbeni, Gemi / Ghami /
        Ghemi), and deciding which spellings are the same place is L3's job with
        the authority list in hand, not a regex's job here.
        """
        slug = re.sub(r"[^\w一-鿿]+", "-", self.subject_name.strip()).strip("-")
        return f"{self.subject_type}:{slug.lower()}"


# ═══════════════════════════════════════════════════════════════════════════
# model call
# ═══════════════════════════════════════════════════════════════════════════

def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
def _chat(system: str, user: str, model: str) -> str:
    """Minimal OpenAI-compatible chat call over stdlib urllib.

    The openai SDK is the obvious choice and is listed in requirements.txt, but
    it is not importable in every environment this runs in, and the request is
    a single POST. Dropping the dependency here costs ~15 lines and removes an
    install-time failure mode from the extraction path.
    """
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{config.QWEN_BASE_URL.rstrip('/')}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {config.DASHSCOPE_API_KEY}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, context=_ssl_context(), timeout=120) as r:
        payload = json.loads(r.read())
    return payload["choices"][0]["message"]["content"]


def _build_system_prompt() -> str:
    preds = "\n".join(f"  {p}: {d}" for p, d in ALL_PREDICATES.items())
    types = "\n".join(f"  {t}: {d}" for t, d in ENTITY_TYPES.items())
    return f"""你是文化景观知识图谱的信息抽取器。从建筑学/考古学文本中抽取结构化三元组。

实体类型（subject_type / object_type 只能取这些）：
{types}

{_TYPE_RULE}

{_SUBJECT_RULE}

谓词（predicate 只能取这些，不得自造）：
{preds}

断言强度 assertion（必填，按作者的措辞判断）：
  asserted     作者以事实陈述
  reported     作者转述他人研究、地方说法或史料
  inferred     作者根据证据推论（"由此推断""说明"）
  hypothesised 作者明确存疑、提问或用"可能/或许/推测"

年代依据 date_basis（仅当谓词涉及年代时填写）：
  dendrochronology 树轮 / radiocarbon 碳十四 / inscription 题记 /
  documentary 文献 / stylistic 风格断代 / tradition 地方传说 /
  inference 推断 / unknown 未说明

铁律：
1. 只抽取文本明确支持的内容，不得补充常识或外部知识。
2. quote 必须是原文的**逐字**片段（可截断），用于人工核验；不得改写。
3. 地名、人名、建筑名保留原文拼写，不要翻译，不要规范化。
4. 作者的推测与断言必须用 assertion 区分开，这一点比抽全更重要。
5. 关系类谓词用 object_name + object_type；字面值谓词用 object_value。二选一。
6. 无法确定实体类型或谓词时，宁可不输出该条。
7. hasName 只用于**别名**（同一对象的另一种拼写或另一个名字），不要复述主语本身，
   也不要拿词源、释义、绰号解释来充当名称。没有别名就不要输出 hasName。
8. 一个主语在同一段里有多个年代（初建、重修、扩建）时，分别输出多条，
   并在 quote 中保留能区分它们的原文。

层级关系必须抽（最常被漏掉）：
  凡文中出现「A 由 B、C、D 构成」「A 分为 B、C 两部分」「B 是 A 的一部分」
  「A 含 B」，都要为每一个下级单元输出一条 partOfUnit：
      subject = 下级单元, predicate = partOfUnit, object_name = 上级单元
  即方向永远是「子 → 父」。同时可另输出上级的 hasSubUnitCount。
  例：「Te 由五个 cluster 构成：Thangka + Yul（含 Sumdu、Töpa）」应输出
      Thangka partOfUnit Te / Yul partOfUnit Te /
      Sumdu partOfUnit Yul / Töpa partOfUnit Yul / Te hasSubUnitCount 5

谓词易混淆处：
  hasSettlementForm 只用于聚落的**形态类型**（密集堡垒式/线型沿街/山顶堡垒/
    崖窟/低密度谷底…）。聚落的形态一律用它，不要用 hasType。
  hasType 用于非形态的类别（如寺院的教派类别、建筑的功能类别）。
  surveyedBy 用于测绘者，包括「作者本人实测」这类表述（此时填作者名）。
  hasNote 是兜底：凡有价值但套不进其他谓词的事实（地方传说、归属争议、
    社会与语言状况、经济变迁），一律用 hasNote 保留，不要因为抽不进结构就丢弃。
  多期营建不要合并成一个 hasTimeSpan，按期分别输出 hasConstructionDate。

输出严格 JSON，不要解释，不要 markdown 包装：
{{"facts":[{{"subject_name":"","subject_type":"","predicate":"",
"object_value":null,"object_name":null,"object_type":null,
"assertion":"","date_basis":null,"quote":""}}]}}"""


def _cache_key(text: str, model: str) -> Path:
    h = hashlib.sha256(f"{PROMPT_VERSION}|{model}|{text}".encode("utf-8")).hexdigest()
    return _CACHE_DIR / f"{h}.json"


def _coerce(raw: dict, locator: str, doc_key: str) -> Optional[CandidateFact]:
    """Validate one model-emitted dict. Returns None if it breaks the contract.

    The model is asked for a closed vocabulary but is not guaranteed to honour
    it, and a hallucinated predicate would create a junk column in the graph
    that no audit query knows to look for. Rejecting here is cheaper than
    normalising later.
    """
    pred = (raw.get("predicate") or "").strip()
    subj = (raw.get("subject_name") or "").strip()
    stype = (raw.get("subject_type") or "").strip()
    if not (pred and subj and stype):
        return None
    if pred not in ALL_PREDICATES:
        log.debug("dropped out-of-vocabulary predicate %r", pred)
        return None
    if stype not in ENTITY_TYPES:
        log.debug("dropped unknown subject_type %r", stype)
        return None

    ov = raw.get("object_value")
    on = raw.get("object_name")
    ot = (raw.get("object_type") or "").strip() or None
    ov = str(ov).strip() if ov not in (None, "") else None
    on = str(on).strip() if on not in (None, "") else None
    if ov is None and on is None:
        return None
    if on and ot not in ENTITY_TYPES:
        return None

    assertion = (raw.get("assertion") or "asserted").strip()
    if assertion not in ASSERTION_CONFIDENCE:
        assertion = "asserted"
    basis = (raw.get("date_basis") or "").strip() or None
    if basis and basis not in DATE_BASIS:
        basis = "unknown"

    return CandidateFact(
        subject_name=subj, subject_type=stype, predicate=pred,
        object_value=ov, object_name=on, object_type=ot,
        assertion=assertion, date_basis=basis,
        quote=(raw.get("quote") or "").strip()[:500],
        locator=locator, doc_key=doc_key,
    )


def extract_facts(
    text: str,
    *,
    locator: str,
    doc_key: str,
    model: Optional[str] = None,
    use_cache: bool = True,
    chat_fn: Optional[Callable[[str, str, str], str]] = None,
) -> list[CandidateFact]:
    """Extract candidate triples from one passage.

    ``chat_fn`` is injectable so the pipeline can be exercised, and the schema
    contract tested, without spending an API call.
    """
    text = (text or "").strip()
    if len(text) < 20:
        return []
    model = model or config.QWEN_MODEL
    caller = chat_fn or _chat

    cache_file = _cache_key(text, model)
    if use_cache and chat_fn is None and cache_file.exists():
        raw_facts = json.loads(cache_file.read_text("utf-8"))
    else:
        try:
            content = caller(_build_system_prompt(), text, model)
        except Exception as e:            # network, auth, rate limit
            log.warning("extraction failed at %s: %s", locator, e)
            return []
        try:
            raw_facts = json.loads(content).get("facts", [])
        except json.JSONDecodeError:
            log.warning("non-JSON response at %s", locator)
            return []
        if use_cache and chat_fn is None:
            cache_file.write_text(json.dumps(raw_facts, ensure_ascii=False, indent=1),
                                  encoding="utf-8")

    out = [f for f in (_coerce(r, locator, doc_key) for r in raw_facts) if f]
    log.info("%s → %d facts (%d raw)", locator, len(out), len(raw_facts))
    return out


# ═══════════════════════════════════════════════════════════════════════════
# candidates → StatementRows
# ═══════════════════════════════════════════════════════════════════════════

def to_statement_rows(
    facts: list[CandidateFact],
    *,
    region: str,
    doc_path: Path,
    model: Optional[str] = None,
) -> list[StatementRow]:
    """Turn candidates into staging rows.

    Evidence is minted **per fact**, not per passage: one paragraph yields
    several claims of differing strength, and the supporting quote belongs to
    the claim rather than to the paragraph. The URI is deterministic, so a
    re-run reuses the same evidence row instead of forking provenance.
    """
    model = model or config.QWEN_MODEL
    base = f"file://{Path(doc_path).resolve()}"
    rows: list[StatementRow] = []

    for i, f in enumerate(facts, start=1):
        digest = hashlib.sha1(
            f"{f.subject_name}|{f.predicate}|{f.object_value}|{f.object_name}"
            .encode("utf-8")).hexdigest()[:10]
        ev_uri = f"{base}#{f.locator.replace(' ', '_')}&fact={digest}"

        common = dict(
            ev_source_uri=ev_uri,
            ev_source_type="document_passage",
            ev_metadata={
                "locator":    f.locator,
                "quote":      f.quote,
                "assertion":  f.assertion,
                "date_basis": f.date_basis,
                "doc_key":    f.doc_key,
                "extractor":  f"{model}|{PROMPT_VERSION}",
            },
            ent_region=region,
            ent_type_abbr=f.subject_type,
            ent_temporal="unk",
            ent_natural_key=f.natural_key(),
        )

        if f.object_name:
            value: dict[str, Any] = {
                "ref_natural_key": CandidateFact(
                    subject_name=f.object_name,
                    subject_type=f.object_type or "pl",
                    predicate="", ).natural_key(),
                "ref_type_abbr": f.object_type or "pl",
                "ref_region":    region,
                "confidence":    f.confidence,
            }
        else:
            value = {"value": f.object_value, "confidence": f.confidence}

        rows.append(StatementRow(**common, stmt_predicate=f.predicate,
                                 stmt_value=value))

        # The subject's surface name, so L3 has something to match on before any
        # authority reconciliation has run.
        rows.append(StatementRow(**common, stmt_predicate="hasName",
                                 stmt_value={"value": f.subject_name,
                                             "confidence": f.confidence}))

        # date_basis is a field on the candidate rather than a predicate the
        # model may choose: as a predicate it competed with hasConstructionDate
        # and the model emitted it *instead of* filling the field, leaving
        # confidence unmodulated. Kept as a field, it drives confidence — and is
        # re-emitted here so the basis stays queryable in the graph too.
        if f.date_basis:
            rows.append(StatementRow(**common, stmt_predicate="hasDateBasis",
                                     stmt_value={"value": f.date_basis,
                                                 "confidence": f.confidence}))
    return rows


def summarise(facts: list[CandidateFact]) -> dict[str, Any]:
    """Counts by predicate / assertion / subject type — the pre-ingest eyeball."""
    def tally(key: Callable[[CandidateFact], Any]) -> dict:
        d: dict[Any, int] = {}
        for f in facts:
            d[key(f)] = d.get(key(f), 0) + 1
        return dict(sorted(d.items(), key=lambda kv: -kv[1]))

    return {
        "n_facts":    len(facts),
        "by_predicate": tally(lambda f: f.predicate),
        "by_assertion": tally(lambda f: f.assertion),
        "by_type":      tally(lambda f: f.subject_type),
        "by_date_basis": tally(lambda f: f.date_basis or "—"),
        "n_subjects":   len({f.natural_key() for f in facts}),
    }
