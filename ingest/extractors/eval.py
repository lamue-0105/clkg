"""Score L2 extraction against a hand-curated gold set.

Prompt changes to an LLM extractor are not obviously improvements — v2 of the
doc_facts prompt fixed entity typing but could as easily have broken something
else, and eyeballing 38 rows does not tell you which. This gives a number to
compare against, and names the specific facts that were missed.

Matching is deliberately loose on the object (free text, phrasing varies) and
strict on subject + predicate, because those are what the graph is keyed on.
Entity type is scored separately: getting clu vs pl wrong is the project's
core-concept error and would otherwise hide inside an object-string match.

    python -m ingest.extractors.eval                    # all gold sets
    python -m ingest.extractors.eval --show-misses
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Optional

from . import doc_facts

GOLD_DIR = Path(__file__).resolve().parent / "gold"


def _norm(s: Optional[str]) -> str:
    """Fold width, case, whitespace and CJK/ASCII punctuation for comparison."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s)).lower()
    s = re.sub(r"[\s\-–—_·、，,。.：:；;（）()「」『』\"']+", "", s)
    return s


def _subject_match(pred_subj: str, gold_subj: str) -> bool:
    a, b = _norm(pred_subj), _norm(gold_subj)
    return bool(a) and bool(b) and (a == b or a in b or b in a)


def _object_match(pred_obj: str, gold_obj: str) -> bool:
    a, b = _norm(pred_obj), _norm(gold_obj)
    if not b:
        return True
    return bool(a) and (a in b or b in a)


def score(gold: dict, facts: list[doc_facts.CandidateFact]) -> dict[str, Any]:
    gold_facts = gold["facts"]
    matched_gold: set[int] = set()
    matched_pred: set[int] = set()
    type_right = type_total = 0

    for gi, g in enumerate(gold_facts):
        for pi, p in enumerate(facts):
            if pi in matched_pred:
                continue
            if p.predicate != g["predicate"]:
                continue
            if not _subject_match(p.subject_name, g["subject"]):
                continue
            if not _object_match(p.object_value or p.object_name or "", g["object"]):
                continue
            matched_gold.add(gi)
            matched_pred.add(pi)
            type_total += 1
            if p.subject_type == g.get("subject_type"):
                type_right += 1
            break

    tp = len(matched_gold)
    precision = tp / len(facts) if facts else 0.0
    recall = tp / len(gold_facts) if gold_facts else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    # Assertion strength is graded separately: it is the field that keeps an
    # author's hypothesis from entering the graph as a fact, so a high F1 with
    # bad assertion labels is worse than it looks.
    assertion_hits: list[tuple[str, str, str, bool]] = []
    for case in gold.get("assertion_cases", []):
        got = None
        for p in facts:
            if not _subject_match(p.subject_name, case["subject"]):
                continue
            blob = f"{p.object_value or ''}{p.object_name or ''}{p.quote}"
            if _norm(case["contains"]) in _norm(blob):
                got = p.assertion
                break
        assertion_hits.append((case["subject"], case["expected"], got or "—",
                               got == case["expected"]))

    return {
        "n_gold": len(gold_facts),
        "n_pred": len(facts),
        "tp": tp,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "type_accuracy": round(type_right / type_total, 3) if type_total else None,
        "missed": [gold_facts[i] for i in range(len(gold_facts)) if i not in matched_gold],
        "spurious": [facts[i] for i in range(len(facts)) if i not in matched_pred],
        "assertion_cases": assertion_hits,
    }


def load_passage(gold: dict) -> str:
    """Re-read the exact source slice a gold set was curated against."""
    src = Path(gold["_source_file"]).expanduser()
    text = src.read_text("utf-8")
    start = text.find(gold["_source_start"])
    if start < 0:
        raise ValueError(f"anchor {gold['_source_start']!r} not found in {src}")
    return text[start:start + gold["_source_length"]]


def run_one(gold_path: Path, *, show_misses: bool) -> dict[str, Any]:
    gold = json.loads(gold_path.read_text("utf-8"))
    passage = load_passage(gold)
    facts = doc_facts.extract_facts(
        passage, locator=gold["locator"], doc_key=gold["doc_key"])
    res = score(gold, facts)

    print(f"\n── {gold_path.name} ──")
    print(f"  gold={res['n_gold']}  predicted={res['n_pred']}  matched={res['tp']}")
    print(f"  precision={res['precision']}  recall={res['recall']}  f1={res['f1']}")
    print(f"  type_accuracy={res['type_accuracy']} "
          f"(clu vs pl on matched facts)")
    if res["assertion_cases"]:
        print("  assertion strength:")
        for subj, exp, got, ok in res["assertion_cases"]:
            print(f"    {'ok ' if ok else 'MISS'} {subj:14} expected={exp:12} got={got}")
    if show_misses:
        if res["missed"]:
            print(f"  missed ({len(res['missed'])}):")
            for m in res["missed"]:
                print(f"    - {m['subject']} {m['predicate']} {m['object']}")
        if res["spurious"]:
            print(f"  not in gold ({len(res['spurious'])}) — may still be correct:")
            for s in res["spurious"][:12]:
                obj = s.object_value or f"→{s.object_name}"
                print(f"    ? {s.subject_name} {s.predicate} {str(obj)[:40]}")
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="clkg-eval")
    ap.add_argument("--show-misses", action="store_true")
    ap.add_argument("--gold", type=Path, default=None,
                    help="a single gold json (default: every file in gold/)")
    args = ap.parse_args(argv)

    paths = [args.gold] if args.gold else sorted(GOLD_DIR.glob("*.json"))
    if not paths:
        print(f"no gold sets in {GOLD_DIR}", file=sys.stderr)
        return 2
    for p in paths:
        run_one(p, show_misses=args.show_misses)
    return 0


if __name__ == "__main__":
    sys.exit(main())
