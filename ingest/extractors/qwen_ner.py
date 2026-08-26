"""Qwen NER over OpenAI-compatible DashScope endpoint.

Disabled by default (ENABLE_NER=0). When disabled, extract_entities() returns
an empty list and the pipeline keeps running. This means you can build out the
tabular + image pipelines today without paying for API calls; flip ENABLE_NER=1
and supply DASHSCOPE_API_KEY once you have a key.

Responses are cached to ~/.cache/clkg/qwen_ner/ keyed by SHA-256 of the input
text + model name, so re-runs cost nothing.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from .. import config

log = logging.getLogger(__name__)

_CACHE_DIR = Path.home() / ".cache" / "clkg" / "qwen_ner"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


_SYSTEM = (
    "你是文化遗产领域命名实体识别专家。从用户文本中抽取命名实体，"
    "类型严格限定为：Place（地点/建筑/地理实体）、Person（人物）、"
    "Period（朝代/历史时期/年代）、Event（事件）。"
    "输出严格 JSON，不要解释，不要 markdown 包装。"
)

_USER_TEMPLATE = (
    "格式：{{\"entities\":[{{\"surface\":\"原文字面\",\"canonical\":\"规范名(可空)\","
    "\"type\":\"Place|Person|Period|Event\",\"confidence\":0.0}}]}}\n\n"
    "文本：\n{text}"
)


def _cache_key(text: str) -> Path:
    h = hashlib.sha256(f"{config.QWEN_MODEL}|{text}".encode("utf-8")).hexdigest()
    return _CACHE_DIR / f"{h}.json"


@retry(stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=1, min=2, max=20))
def _call_qwen(text: str) -> list[dict[str, Any]]:
    # Imported lazily so the package imports cleanly even without `openai` installed.
    from openai import OpenAI

    client = OpenAI(api_key=config.DASHSCOPE_API_KEY, base_url=config.QWEN_BASE_URL)
    resp = client.chat.completions.create(
        model=config.QWEN_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": _USER_TEMPLATE.format(text=text)},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    parsed = json.loads(resp.choices[0].message.content)
    return parsed.get("entities", [])


def extract_entities(text: str) -> list[dict[str, Any]]:
    text = (text or "").strip()
    if not text or len(text) < 4:
        return []

    if not config.ENABLE_NER:
        # Silent no-op when disabled (most common case during early development).
        return []

    cache_file = _cache_key(text)
    if cache_file.exists():
        return json.loads(cache_file.read_text("utf-8"))

    try:
        ents = _call_qwen(text)
    except Exception as e:
        log.warning("Qwen NER failed for text len=%d: %s", len(text), e)
        return []

    cache_file.write_text(json.dumps(ents, ensure_ascii=False, indent=2), "utf-8")
    return ents
