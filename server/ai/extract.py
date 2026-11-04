"""Document text extraction for F1 (SPEC §10.1.1, lean: no OCR, no figures).

PDF (pypdf, "Hal. N" labels, pages < 80 chars skipped with a warning), PPTX
(slide text + notes, "Slide N" labels), DOCX (paragraphs + tables in order),
XLSX (plain text rows, stdlib zipfile + XML), TXT/MD (as is), PNG/JPG (one
VISION call). Total text is capped at MAX_TOTAL_CHARS.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from server.ai.errors import AIError

log = logging.getLogger("orvina.ai")

MAX_TOTAL_CHARS = 120_000
MIN_PDF_PAGE_CHARS = 80

Handler = Callable[..., tuple[str, list[str]]]


def _pdf(path: str) -> tuple[str, list[str]]:
    from pypdf import PdfReader

    reader = PdfReader(path)
    parts: list[str] = []
    warnings: list[str] = []
    for i, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        if len(text) < MIN_PDF_PAGE_CHARS:
            log.info("PDF page %d has <%d chars, skipped (no OCR in lean)", i, MIN_PDF_PAGE_CHARS)
            warnings.append("pdf_page_skipped")
            continue
        parts.append(f"## Hal. {i}\n\n{text}")
    return "\n\n".join(parts), warnings


def _pptx(path: str) -> tuple[str, list[str]]:
    from pptx import Presentation

    prs = Presentation(path)
    parts: list[str] = []
    warnings: list[str] = []
    for i, slide in enumerate(prs.slides, 1):
        texts: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                t = "\n".join(p.text for p in shape.text_frame.paragraphs if p.text.strip())
                if t.strip():
                    texts.append(t.strip())
            if shape.has_table:
                for row in shape.table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    if any(cells):
                        texts.append(" | ".join(cells))
        notes = ""
        if slide.has_notes_slide:
            notes = (slide.notes_slide.notes_text_frame.text or "").strip()
        body = "\n\n".join(texts)
        if notes:
            body = f"{body}\n\nCatatan: {notes}" if body else f"Catatan: {notes}"
        if not body.strip():
            log.info("PPTX slide %d is empty, skipped", i)
            warnings.append("pptx_slide_empty")
            continue
        parts.append(f"## Slide {i}\n\n{body.strip()}")
    return "\n\n".join(parts), warnings


def _docx(path: str) -> tuple[str, list[str]]:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(path)
    parts: list[str] = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = Paragraph(child, doc).text.strip()
            if text:
                parts.append(text)
        elif tag == "tbl":
            table = Table(child, doc)
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells]
                if any(cells):
                    parts.append(" | ".join(cells))
    return "\n".join(parts), []


def _text(path: str) -> tuple[str, list[str]]:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read().strip(), []


def _image(path: str, llm: Any, calls: list[dict]) -> tuple[str, list[str]]:
    from server.ai.prompts import VISION_TEXT_PROMPT

    out = llm.chat(
        "VISION",
        [{"role": "user", "content": VISION_TEXT_PROMPT.format(language="id")}],
        images=[path],
        feature="extract_image",
        calls=calls,
    )
    return str(out).strip(), []


def _xlsx(path: str) -> tuple[str, list[str]]:
    """Spreadsheet as plain text rows (stdlib only: zipfile + XML, no new dep)."""
    import zipfile
    from xml.etree import ElementTree

    m_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    parts: list[str] = []
    warnings: list[str] = []
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ElementTree.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.iter(f"{{{m_ns}}}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{m_ns}}}t")))
        sheets = sorted(n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
        for i, sheet in enumerate(sheets, 1):
            rows_out: list[str] = []
            root = ElementTree.fromstring(z.read(sheet))
            for row in root.iter(f"{{{m_ns}}}row"):
                cells: list[str] = []
                for c in row.iter(f"{{{m_ns}}}c"):
                    t = c.get("t")
                    v = c.find(f"{{{m_ns}}}v")
                    if t == "inlineStr":
                        txt = "".join(x.text or "" for x in c.iter(f"{{{m_ns}}}t"))
                    elif v is not None and v.text is not None:
                        txt = shared[int(v.text)] if t == "s" else v.text
                    else:
                        txt = ""
                    cells.append(txt.strip())
                if any(cells):
                    rows_out.append(" | ".join(cells))
            if rows_out:
                parts.append(f"## Sheet {i}\n\n" + "\n".join(rows_out))
            else:
                log.info("XLSX sheet %d is empty, skipped", i)
                warnings.append("xlsx_sheet_empty")
    return "\n\n".join(parts), warnings


def _handler_for(name: str, mime: str) -> str | None:
    m = (mime or "").lower()
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if "pdf" in m or ext == "pdf":
        return "pdf"
    if "presentationml" in m or ext == "pptx":
        return "pptx"
    if "wordprocessingml" in m or ext == "docx":
        return "docx"
    if "spreadsheetml" in m or ext in ("xlsx",):
        return "xlsx"
    if m in ("text/plain", "text/markdown") or ext in ("txt", "md"):
        return "text"
    if m in ("image/png", "image/jpeg") or ext in ("png", "jpg", "jpeg"):
        return "image"
    return None


def extract_file(path: str, name: str, mime: str, *, llm: Any, calls: list[dict]) -> str:
    """Extract one file to labelled text. Raises AIError on unsupported format
    or a failed read."""
    kind = _handler_for(name, mime)
    if kind is None:
        raise AIError("unsupported_format", {"name": name})
    if kind == "image":
        text, _ = _image(path, llm, calls)
    elif kind == "pdf":
        text, _ = _pdf(path)
    elif kind == "pptx":
        text, _ = _pptx(path)
    elif kind == "docx":
        text, _ = _docx(path)
    elif kind == "xlsx":
        text, _ = _xlsx(path)
    else:
        text, _ = _text(path)
    return text.strip()


def extract_files(files: list[dict], *, llm: Any, calls: list[dict]) -> tuple[str, list[str], list[dict]]:
    """Extract all files. Returns (full_text, warnings, sources[{label, text}]).
    The combined text is capped at MAX_TOTAL_CHARS."""
    texts: list[str] = []
    warnings: list[str] = []
    sources: list[dict] = []
    for f in files:
        name = f.get("name") or str(f.get("path", "?"))
        try:
            text = extract_file(f["path"], name, f.get("mime", ""), llm=llm, calls=calls)
        except AIError:
            raise
        except Exception as exc:
            raise AIError("extract_failed", {"name": name, "detail": str(exc)[:200]}) from exc
        if not text:
            log.info("%s: no extractable text, skipped", name)
            warnings.append("file_no_text")
            continue
        texts.append(text)
        sources.append({"label": name, "text": text})
    full = "\n\n".join(texts)
    if len(full) > MAX_TOTAL_CHARS:
        full = full[:MAX_TOTAL_CHARS]
        warnings.append("text_capped")
    return full, warnings, sources


__all__ = ["MAX_TOTAL_CHARS", "extract_file", "extract_files"]
