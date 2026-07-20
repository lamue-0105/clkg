"""Document connector — long-form sources (books, reports, .docx) → passages.

This is layer L1 of the document pipeline. It is deliberately *semantics-free*:
it turns a file into a stream of located text passages and emits only
bibliographic statements about the document itself. Extracting facts *from* the
passages is L2 (see ingest/extractors/), and binding those facts to existing
entities is L3.

Two outputs, two consumers:

    describe(path)          → cheap probe: page count, text-layer coverage.
                              Run this first to decide the extraction route.
    read_passages(path)     → list[Passage] for L2. Cached on disk.
    ingest_document(path)   → list[StatementRow] for the doc entity itself.

Why the split: a scanned book has no text layer, so read_passages() cannot
produce text for it without an OCR/VLM pass — which costs money and should be
an explicit, resumable decision rather than a side effect of opening a file.
Pages that need one come back with kind="needs_ocr" and empty text; supply an
``ocr_fn`` to fill them in, and the result is cached so it is paid for once.

Copyright note: passages are an *intermediate*. They are cached on local disk
(outside the repo, outside the DB) so that re-runs are free. They are never
written to entity_statement — only extracted facts plus a page locator are.
This keeps in-copyright sources usable without redistributing their text.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from ..staging import StatementRow

log = logging.getLogger(__name__)

_CACHE_DIR = Path.home() / ".cache" / "clkg" / "doc_passages"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# A page yielding fewer than this many characters is treated as image-only.
# Scanned books routinely return a stray ligature or page number, so 0 is too
# strict a threshold.
MIN_CHARS_PER_PAGE = 40

# Figure/plate captions in academic books are near-universally "<chapter>.<n>".
# Matched at the start of a paragraph, e.g. "4.130. Lo Manthang plan, ..." or
# "7.99 Temple plans (not to scale)".
_CAPTION_RE = re.compile(r"^(\d{1,2}\.\d{1,3})[.\s]")

# A heading is short, has no terminal punctuation, and is often numbered.
_HEADING_RE = re.compile(r"^(\d{1,2}\.\s+)?[A-Z0-9][^.!?]{0,60}$")

_SUPPORTED = {".pdf", ".docx", ".txt", ".md"}


# ═══════════════════════════════════════════════════════════════════════════
# Passage
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Passage:
    """One citable unit of text within a document.

    ``page`` is the *printed* page number (what a reader would cite);
    ``pdf_page`` is the 1-based physical page in the file. They differ by
    ``page_offset`` whenever front matter is unpaginated.
    """
    doc_key: str
    ordinal: int              # 1-based, across the whole document
    pdf_page: int             # physical page, 1-based
    page: Optional[int]       # printed page number, or None for .docx/.txt
    kind: str                 # body | caption | heading | needs_ocr
    text: str
    locator: str              # citable string, e.g. "p.116" / "p.116 fig.4.130"
    source: str               # text_layer | ocr | docx | plain
    figure_id: Optional[str] = None   # "4.130" when kind == caption
    meta: dict = field(default_factory=dict)

    def as_evidence_uri(self, base: str) -> str:
        """Stable, human-resolvable evidence URI for statements from this passage."""
        return f"{base}#page={self.pdf_page}&passage={self.ordinal}"


# ═══════════════════════════════════════════════════════════════════════════
# probing
# ═══════════════════════════════════════════════════════════════════════════

def _require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise RuntimeError(
            f"'{tool}' not found. Install poppler-utils "
            f"(macOS: brew install poppler)."
        )
    return path


def _pdfinfo(path: Path) -> dict[str, str]:
    out = subprocess.run([_require("pdfinfo"), str(path)],
                         capture_output=True, text=True, check=True).stdout
    info: dict[str, str] = {}
    for line in out.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            info[k.strip()] = v.strip()
    return info


def _pdf_page_texts(path: Path, first: int = 1, last: Optional[int] = None) -> list[str]:
    """Extract the text layer page by page. One subprocess call, split on \\f."""
    cmd = [_require("pdftotext"), "-layout", "-f", str(first)]
    if last:
        cmd += ["-l", str(last)]
    cmd += [str(path), "-"]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    pages = out.split("\f")
    # pdftotext emits a trailing form feed after the final page.
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def describe(path: Path) -> dict[str, Any]:
    """Cheap probe. Tells you whether this file has a usable text layer.

    Returns a dict with ``n_pages``, ``text_pages``, ``coverage`` (0..1) and the
    raw container metadata. ``coverage < 0.1`` means a scan: budget for OCR.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    base: dict[str, Any] = {
        "path": str(path),
        "suffix": suffix,
        "size_bytes": path.stat().st_size,
    }

    if suffix != ".pdf":
        return base | {"n_pages": None, "text_pages": None, "coverage": 1.0,
                       "route": "text_layer", "metadata": {}}

    info = _pdfinfo(path)
    n_pages = int(info.get("Pages", "0") or 0)
    texts = _pdf_page_texts(path)
    text_pages = sum(1 for t in texts if len(t.strip()) >= MIN_CHARS_PER_PAGE)
    coverage = (text_pages / n_pages) if n_pages else 0.0
    return base | {
        "n_pages": n_pages,
        "text_pages": text_pages,
        "coverage": round(coverage, 4),
        "route": "text_layer" if coverage >= 0.5 else "ocr",
        "metadata": info,
    }


# ═══════════════════════════════════════════════════════════════════════════
# passage segmentation
# ═══════════════════════════════════════════════════════════════════════════

def _classify(para: str) -> tuple[str, Optional[str]]:
    """(kind, figure_id) for one paragraph."""
    m = _CAPTION_RE.match(para)
    if m:
        return "caption", m.group(1)
    if len(para) <= 60 and _HEADING_RE.match(para) and not para.endswith((".", ",")):
        return "heading", None
    return "body", None


def _norm_furniture(line: str) -> str:
    """Normalise a candidate running header/footer: digits out, spacing collapsed.

    Page numbers change every page, so "30 | Chapter 1: X" and "31 | Chapter 1: X"
    must normalise to the same key for the frequency count to see them.
    """
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", line)).strip().lower()


def find_running_furniture(page_texts: Iterable[str],
                           min_ratio: float = 0.02,
                           min_pages: int = 4) -> set[str]:
    """Normalised first/last lines that repeat across pages — headers and footers.

    Page furniture is not content: left in, it adds one junk passage per page and
    pollutes every downstream extraction. Detected by repetition rather than by
    regex so it works regardless of the publisher's house style.

    The threshold is deliberately low. Books commonly alternate footers by parity
    (chapter title verso, section title recto) and reset them every chapter, so a
    given footer may cover only a few percent of a long book — a 20%-of-pages rule
    finds nothing at all on an 800-page volume. A content line that happens to be
    the first or last line of four different pages, identical after digit
    normalisation, is vanishingly rare, so false positives stay negligible.
    """
    pages = [t for t in page_texts]
    counts: dict[str, int] = {}
    for text in pages:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            continue
        for cand in {lines[0], lines[-1]}:
            key = _norm_furniture(cand)
            if key and len(key) <= 120:
                counts[key] = counts.get(key, 0) + 1
    threshold = max(min_pages, int(len(pages) * min_ratio))
    return {k for k, n in counts.items() if n >= threshold}


_FURNITURE_MEMO: dict[tuple[str, int, int], set[str]] = {}


def _furniture_for(path: Path, page_texts: list[str],
                   is_full_document: bool) -> set[str]:
    """Furniture for a whole file, memoised per (path, size, mtime).

    Learning it needs the whole document: a 5-page pilot slice has too few
    samples for the frequency test to fire. Without the memo, iterating on a
    small slice would re-extract the entire file on every call — for the 851-page
    test book that is the difference between 3.6s and 0.02s per iteration.
    """
    st = path.stat()
    key = (str(path.resolve()), st.st_size, int(st.st_mtime))
    if key not in _FURNITURE_MEMO:
        texts = page_texts if is_full_document else _pdf_page_texts(path)
        _FURNITURE_MEMO[key] = find_running_furniture(texts)
    return _FURNITURE_MEMO[key]


def _strip_furniture(page_text: str, furniture: set[str]) -> str:
    if not furniture:
        return page_text
    lines = page_text.splitlines()
    # Only the outermost non-blank lines can be furniture; never touch the middle.
    for idx in (0, -1):
        while lines:
            probe = next((i for i in (range(len(lines)) if idx == 0
                                      else range(len(lines) - 1, -1, -1))
                          if lines[i].strip()), None)
            if probe is None or _norm_furniture(lines[probe]) not in furniture:
                break
            lines.pop(probe)
    return "\n".join(lines)


def _split_paragraphs(page_text: str) -> list[str]:
    """Blank-line paragraph split, with de-hyphenation and whitespace collapse."""
    paras: list[str] = []
    for raw in re.split(r"\n\s*\n", page_text):
        # join words broken across a line end, then collapse remaining newlines
        joined = re.sub(r"(\w)-\n\s*(\w)", r"\1\2", raw)
        joined = re.sub(r"\s*\n\s*", " ", joined)
        joined = re.sub(r"[ \t]{2,}", " ", joined).strip()
        if joined:
            paras.append(joined)
    return paras


def _cache_key(path: Path, page_offset: int, doc_key: str) -> Path:
    st = path.stat()
    sig = f"{path.resolve()}|{st.st_size}|{int(st.st_mtime)}|{page_offset}|{doc_key}"
    return _CACHE_DIR / f"{hashlib.sha256(sig.encode()).hexdigest()}.json"


def _load_cache(cache_file: Path) -> Optional[list[Passage]]:
    if not cache_file.exists():
        return None
    try:
        raw = json.loads(cache_file.read_text("utf-8"))
        return [Passage(**d) for d in raw]
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        log.warning("Corrupt passage cache %s (%s) — re-reading", cache_file, e)
        return None


def _save_cache(cache_file: Path, passages: list[Passage]) -> None:
    cache_file.write_text(
        json.dumps([asdict(p) for p in passages], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


def read_passages(
    path: Path,
    *,
    doc_key: str,
    page_offset: int = 0,
    pages: Optional[tuple[int, int]] = None,
    ocr_fn: Optional[Callable[[Path, int], str]] = None,
    use_cache: bool = True,
) -> list[Passage]:
    """Segment a document into located passages.

    Parameters
    ----------
    doc_key
        natural_key of the parent ``doc`` entity. Baked into each Passage so
        L2's statements can point back without re-deriving it.
    page_offset
        printed_page = pdf_page + page_offset. Zero when the scan includes the
        cover as page 1 and the printed numbering agrees (verify on a spread!).
    pages
        (first, last) 1-based physical page range. Useful for pilot slices.
    ocr_fn
        ``(pdf_path, pdf_page) -> text`` used for pages with no text layer.
        Omit to leave those pages as ``kind="needs_ocr"`` with empty text.
    """
    path = Path(path)
    if path.suffix.lower() not in _SUPPORTED:
        raise ValueError(f"Unsupported document type {path.suffix!r}; "
                         f"expected one of {sorted(_SUPPORTED)}")

    cache_file = _cache_key(path, page_offset, doc_key)
    if use_cache and ocr_fn is None:
        cached = _load_cache(cache_file)
        if cached is not None:
            log.info("passages: %d from cache (%s)", len(cached), path.name)
            return _slice_pages(cached, pages)

    if path.suffix.lower() == ".pdf":
        passages = _read_pdf(path, doc_key, page_offset, pages, ocr_fn)
    elif path.suffix.lower() == ".docx":
        passages = _read_docx(path, doc_key)
    else:
        passages = _read_plain(path, doc_key)

    # Only ever cache a whole document. The cache key cannot include ``pages``
    # without multiplying entries per slice, so caching a slice under it would
    # make a later full read silently return just that slice.
    if use_cache and pages is None:
        _save_cache(cache_file, passages)
    log.info("passages: %d from %s (%d need OCR)", len(passages), path.name,
             sum(1 for p in passages if p.kind == "needs_ocr"))
    return passages


def _slice_pages(passages: list[Passage],
                 pages: Optional[tuple[int, int]]) -> list[Passage]:
    if not pages:
        return passages
    first, last = pages
    return [p for p in passages if first <= p.pdf_page <= last]


def _read_pdf(
    path: Path,
    doc_key: str,
    page_offset: int,
    pages: Optional[tuple[int, int]],
    ocr_fn: Optional[Callable[[Path, int], str]],
) -> list[Passage]:
    first, last = (pages or (1, None))
    page_texts = _pdf_page_texts(path, first=first, last=last)
    furniture = _furniture_for(path, page_texts, is_full_document=pages is None)

    out: list[Passage] = []
    ordinal = 0
    for i, page_text in enumerate(page_texts):
        pdf_page = first + i
        printed = pdf_page + page_offset
        source = "text_layer"
        page_text = _strip_furniture(page_text, furniture)

        if len(page_text.strip()) < MIN_CHARS_PER_PAGE:
            if ocr_fn is None:
                ordinal += 1
                out.append(Passage(
                    doc_key=doc_key, ordinal=ordinal, pdf_page=pdf_page,
                    page=printed, kind="needs_ocr", text="",
                    locator=f"p.{printed}", source="none",
                ))
                continue
            page_text = ocr_fn(path, pdf_page) or ""
            source = "ocr"

        for para in _split_paragraphs(page_text):
            kind, fig = _classify(para)
            ordinal += 1
            locator = f"p.{printed}" + (f" fig.{fig}" if fig else "")
            out.append(Passage(
                doc_key=doc_key, ordinal=ordinal, pdf_page=pdf_page,
                page=printed, kind=kind, text=para, locator=locator,
                source=source, figure_id=fig,
            ))
    return out


def _read_docx(path: Path, doc_key: str) -> list[Passage]:
    try:
        import docx  # python-docx
    except ImportError as e:
        raise RuntimeError("python-docx is required for .docx "
                           "(pip install python-docx)") from e
    d = docx.Document(str(path))
    out: list[Passage] = []
    for i, para in enumerate(d.paragraphs, start=1):
        text = re.sub(r"\s+", " ", para.text).strip()
        if not text:
            continue
        style = (para.style.name or "").lower() if para.style else ""
        kind = "heading" if style.startswith("heading") else _classify(text)[0]
        _, fig = _classify(text)
        out.append(Passage(
            doc_key=doc_key, ordinal=len(out) + 1, pdf_page=1, page=None,
            kind=kind, text=text, locator=f"¶{i}", source="docx",
            figure_id=fig, meta={"style": style} if style else {},
        ))
    return out


def _read_plain(path: Path, doc_key: str) -> list[Passage]:
    text = path.read_text("utf-8", errors="replace")
    out: list[Passage] = []
    for para in _split_paragraphs(text):
        kind, fig = _classify(para)
        out.append(Passage(
            doc_key=doc_key, ordinal=len(out) + 1, pdf_page=1, page=None,
            kind=kind, text=para, locator=f"¶{len(out) + 1}", source="plain",
            figure_id=fig,
        ))
    return out


# ═══════════════════════════════════════════════════════════════════════════
# bibliographic statements about the document itself
# ═══════════════════════════════════════════════════════════════════════════

# Container metadata is written by whatever produced the file and is routinely
# wrong for scans (CamScanner sets Author to itself), so anything the caller
# passes explicitly wins, and the provenance of each field is recorded.
_BIB_PREDICATES = {
    "title":            "hasTitle",
    "author":           "hasAuthor",
    "publisher":        "hasPublisher",
    "publication_year": "hasPublicationYear",
    "identifier":       "hasIdentifier",
    "language":         "hasLanguage",
    "series":           "hasSeries",
    "doc_type":         "hasType",
}


def ingest_document(
    path: Path,
    *,
    region: str,
    doc_key: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
    temporal: str = "unk",
) -> list[StatementRow]:
    """Emit bibliographic StatementRows for the ``doc`` entity.

    Deliberately does NOT emit hasFullText: for in-copyright sources the KG
    stores extracted facts plus a page locator, not the text itself. Passages
    live in the on-disk cache and never reach the database.

    ``meta`` overrides container metadata, e.g.::

        meta={"title": "Mustang Building", "author": "John Harrison",
              "publication_year": "2019", "identifier": "978-9937-0-6942-7"}
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    meta = dict(meta or {})
    doc_key = doc_key or f"doc:{path.stem}"

    container: dict[str, str] = {}
    n_pages: Optional[int] = None
    if path.suffix.lower() == ".pdf":
        info = _pdfinfo(path)
        n_pages = int(info.get("Pages", "0") or 0) or None
        if info.get("Title"):
            container["title"] = info["Title"]
        if info.get("Author"):
            container["author"] = info["Author"]

    ev_uri = f"file://{path.resolve()}"
    common = dict(
        ev_source_uri=ev_uri,
        ev_source_type="document_file",
        ev_metadata={
            "producer": (container or {}).get("producer"),
            "size_bytes": path.stat().st_size,
            "n_pages": n_pages,
            "meta_source": {k: ("explicit" if k in meta else "container")
                            for k in set(meta) | set(container)},
        },
        ent_region=region,
        ent_type_abbr="doc",
        ent_temporal=temporal,
        ent_natural_key=doc_key,
    )

    rows: list[StatementRow] = []
    merged = {**container, **meta}          # explicit wins over container
    for field_name, predicate in _BIB_PREDICATES.items():
        value = merged.get(field_name)
        if value:
            rows.append(StatementRow(**common, stmt_predicate=predicate,
                                     stmt_value={"value": str(value)}))

    label = merged.get("title") or path.stem
    rows.append(StatementRow(**common, stmt_predicate="hasName",
                             stmt_value={"value": label}))
    rows.append(StatementRow(**common, stmt_predicate="hasFileName",
                             stmt_value={"value": path.name}))
    rows.append(StatementRow(**common, stmt_predicate="hasFilePath",
                             stmt_value={"value": str(path.resolve())}))
    rows.append(StatementRow(**common, stmt_predicate="hasFileType",
                             stmt_value={"value": path.suffix.lower().lstrip(".")}))
    rows.append(StatementRow(**common, stmt_predicate="hasFileSize",
                             stmt_value={"value": str(path.stat().st_size)}))
    if n_pages:
        rows.append(StatementRow(**common, stmt_predicate="hasPageCount",
                                 stmt_value={"value": str(n_pages)}))
    return rows


# ═══════════════════════════════════════════════════════════════════════════
# discovery
# ═══════════════════════════════════════════════════════════════════════════

def discover_documents(root: Path) -> list[Path]:
    """All supported documents under a folder, sorted, recursively."""
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*")
                  if p.is_file() and p.suffix.lower() in _SUPPORTED
                  and not p.name.startswith("~$"))
