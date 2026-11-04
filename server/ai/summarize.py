"""F1 summarize pipeline (SPEC §10.1, lean: no figures stage, figures: []).

Stages (each announced via on_stage): extract -> chunk -> map -> reduce ->
check -> deadlines. Returns {content_md, figures: [], sources, deadlines,
warnings, warning, ai_calls}.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import logging
import re
from collections.abc import Callable
from typing import Any

from server.ai import prompts
from server.ai.errors import AIError

log = logging.getLogger("orvina.ai")

STAGES = ("extract", "chunk", "map", "reduce", "check", "deadlines")
CHUNK_TARGET = 6000
_LABEL_LINE = re.compile(r"^## (Hal\. \d+|Slide \d+)\b")
WIB = dt.timezone(dt.timedelta(hours=7))

# QA: agenda categories (owner decision 2026-11-03).
KINDS = ("kelas", "belajar", "acara", "tenggat")
SUBKINDS = ("tugas", "kuis", "ujian")


def _default_llm() -> Any:
    from server.ai import llm

    return llm


def chunk_text(text: str, target: int = CHUNK_TARGET) -> list[str]:
    """~target-char chunks on label ("## Hal. N" / "## Slide N") boundaries."""
    lines = text.splitlines()
    sections: list[list[str]] = []
    cur: list[str] = []
    for line in lines:
        if _LABEL_LINE.match(line) and cur:
            sections.append(cur)
            cur = []
        cur.append(line)
    if cur:
        sections.append(cur)

    chunks: list[str] = []
    buf = ""
    for sec in sections:
        s = "\n".join(sec).strip()
        if not s:
            continue
        while len(s) > target * 2:  # hard-split an oversized section
            cut = s.rfind("\n", 0, target * 2)
            if cut < target // 2:
                cut = target * 2
            chunks.append(s[:cut].strip())
            s = s[cut:].strip()
        if buf and len(buf) + len(s) + 2 > target:
            chunks.append(buf)
            buf = s
        else:
            buf = f"{buf}\n\n{s}".strip()
    if buf:
        chunks.append(buf)
    return [c for c in chunks if c]


def _format_issues(md: str) -> list[str]:
    """Python format check (SPEC §10.1.6): closed fences, balanced $ / $$.

    Math is only checked outside code fences.
    """
    issues: list[str] = []
    fence_count = 0
    outside: list[str] = []
    in_fence = False
    for line in md.splitlines():
        if line.lstrip().startswith("```"):
            fence_count += 1
            in_fence = not in_fence
            continue
        if not in_fence:
            outside.append(line)
    if fence_count % 2 != 0:
        issues.append("unclosed code fence")
    text = "\n".join(outside)
    if text.count("$$") % 2 != 0:
        issues.append("unbalanced $$")
    if text.replace("$$", "").count("$") % 2 != 0:
        issues.append("unbalanced $")
    return issues


def _format_check(md: str, *, llm: Any, calls: list[dict], lang: str) -> tuple[str, bool]:
    """Returns (md, still_broken). One CHECK repair attempt if broken."""
    issues = _format_issues(md)
    if not issues:
        return md, False
    repaired = llm.chat(
        "CHECK",
        [
            {"role": "system", "content": prompts.REPAIR_PROMPT.format(language=lang)},
            {"role": "user", "content": f"Issues: {', '.join(issues)}\n\nDocument:\n\n{md}"},
        ],
        feature="format_repair",
        calls=calls,
    )
    repaired = str(repaired).strip()
    return (repaired, False) if not _format_issues(repaired) else (md, True)


def _fmt_utc(d: dt.datetime) -> str:
    d = d.astimezone(dt.timezone.utc)
    return f"{d.strftime('%Y-%m-%dT%H:%M:%S')}.{d.microsecond // 1000:03d}Z"


def _parse_time(value: Any) -> str | None:
    """'09.00' / '09:00' / '0900' -> 'HH:MM' (WIB), None when invalid."""
    if not value:
        return None
    m = re.fullmatch(r"(\d{1,2})[:.](\d{2})", str(value).strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return None
    return f"{h:02d}:{mi:02d}"


def _clean_deadlines(raw: Any, today: dt.date) -> tuple[list[dict], list[str]]:
    """Validate the model output; drop deadlines without a resolvable date.

    Returns (deadlines, warning_codes). Dates are stored date-only (midnight
    WIB) or as UTC ISO with the WIB time applied.
    """
    out: list[dict] = []
    dropped = 0
    for d in raw if isinstance(raw, list) else []:
        if not isinstance(d, dict):
            dropped += 1
            continue
        title = str(d.get("title") or "").strip()[:150]
        try:
            day = dt.date.fromisoformat(str(d.get("date") or "").strip()[:10])
        except ValueError:
            dropped += 1
            continue
        if not title:
            dropped += 1
            continue
        kind = d.get("kind") if d.get("kind") in KINDS else "tenggat"
        subkind = d.get("subkind") if kind == "tenggat" and d.get("subkind") in SUBKINDS else None
        time = _parse_time(d.get("time"))
        if time:
            h, mi = (int(x) for x in time.split(":"))
            start = _fmt_utc(dt.datetime.combine(day, dt.time(h, mi), tzinfo=WIB))
        else:
            start = day.isoformat()  # date-only: _stored_dt reads it as midnight WIB
        out.append(
            {
                "title": title,
                "kind": kind,
                "subkind": subkind,
                "start_at": start,
                "end_at": None,
                "evidence": str(d.get("evidence", "")).strip()[:500],
            }
        )
    warns: list[str] = []
    if dropped:
        warns.append("deadline_dropped")
    return out, warns


_DEADLINE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "kind": {"type": "string"},
            "subkind": {"type": ["string", "null"]},
            "date": {"type": "string"},
            "time": {"type": ["string", "null"]},
            "evidence": {"type": "string"},
        },
        "required": ["title", "date", "evidence"],
    },
}


# BUG-01 fallback: parse dates out of the "Tanggal & tenggat" / "Dates &
# deadlines" section of the summary (Indonesian and English formats).
_ID_MONTHS = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
}
_EN_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_DEDLINE_HEADING = re.compile(r"^#{1,6}\s*(tanggal\s*&\s*tenggat|dates\s*&\s*deadlines)\s*$", re.IGNORECASE)
_ID_DATE = re.compile(
    r"(\d{1,2})\s+([a-z]{3,9})(?:\s+(\d{4}))?(?:\s*(?:pukul|jam|,|sekitar|selesai)\s*(\d{1,2})[:.](\d{2}))?",
    re.IGNORECASE,
)
_EN_DATE = re.compile(
    r"([a-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(?:\bof\s+)?(\d{4})"
    r"(?:\s*(?:at|,|sekitar|pukul)\s*(\d{1,2})[:.](\d{2}))?",
    re.IGNORECASE,
)


def _next_occurrence(month: int, day: int | None, year: int | None, today: dt.date) -> dt.date | None:
    if year is None:
        year = today.year + (1 if (month, day or 1) < (today.month, today.day) else 0)
    try:
        return dt.date(year, month, day or 1)
    except ValueError:
        return None


def _subkind_from_text(line: str) -> str:
    low = line.lower()
    if "kuis" in low:
        return "kuis"
    if "ujian" in low or "uts" in low or "uas" in low or "exam" in low:
        return "ujian"
    return "tugas"


def fallback_deadlines(content_md: str, today: dt.date) -> list[dict]:
    """BUG-01: last-resort parser when the model JSON is unreadable."""
    lines = content_md.splitlines()
    section: list[str] = []
    in_section = False
    for line in lines:
        if _DEDLINE_HEADING.match(line.strip()):
            in_section = True
            continue
        if in_section and re.match(r"^#{1,6}\s", line.strip()):
            break
        if in_section:
            section.append(line)
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for raw in section:
        line = raw.strip().lstrip("-*• ").strip()
        if not line:
            continue
        m = _ID_DATE.search(line)
        month, day, year, h, mi = None, None, None, None, None
        if m and (m.group(2).lower() in _ID_MONTHS):
            month, day = _ID_MONTHS[m.group(2).lower()], int(m.group(1))
            year = int(m.group(3)) if m.group(3) else None
            h = int(m.group(4)) if m.group(4) else None
            mi = int(m.group(5)) if m.group(5) else None
        else:
            m = _EN_DATE.search(line)
            if m and (m.group(1).lower() in _EN_MONTHS):
                month, day = _EN_MONTHS[m.group(1).lower()], int(m.group(2))
                year = int(m.group(3)) if m.group(3) else None
                h = int(m.group(4)) if m.group(4) else None
                mi = int(m.group(5)) if m.group(5) else None
        if month is None:
            continue
        day = _next_occurrence(month, day, year, today)
        if day is None:
            continue
        title = re.sub(r"\s+", " ", line).strip(" -:—\t")[:150]
        if not title or title.lower() in ("tanggal & tenggat", "dates & deadlines"):
            title = "Tenggat"
        key = (day.isoformat(), title.lower())
        if key in seen:
            continue
        seen.add(key)
        start = day.isoformat()
        if h is not None and mi is not None and h <= 23 and mi <= 59:
            start = _fmt_utc(dt.datetime.combine(day, dt.time(h, mi), tzinfo=WIB))
        out.append(
            {
                "title": title,
                "kind": "tenggat",
                "subkind": _subkind_from_text(line),
                "start_at": start,
                "end_at": None,
                "evidence": line[:500],
            }
        )
    return out


def summarize(
    job_id: str,
    files: list[dict],
    options: dict,
    on_stage: Callable[[str], None],
    *,
    llm: Any = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """SPEC §7 F1. files [{path, name, mime}], options {style, lang, ...}.

    `llm` is injectable for tests (FakeLLM); the default is server.ai.llm.
    `on_progress(done_chunks, total_chunks)` reports map-loop progress
    (L7a); a progress error never fails the job.
    """
    if llm is None:
        llm = _default_llm()
    opts = options or {}
    style = opts.get("style", "terstruktur")
    if style not in prompts.STYLES:
        style = "terstruktur"
    lang = opts.get("lang", "id")
    if lang not in ("id", "en"):
        lang = "id"
    user_note = str(opts.get("notes") or "").strip()[:500]  # FEAT-01 user note
    include_deadlines = bool(opts.get("include_deadlines", True))

    def _progress(done: int, total: int) -> None:
        if on_progress is None:
            return
        with contextlib.suppress(Exception):  # a progress error never fails the job (L7a)
            on_progress(done, total)

    from server.ai import extract

    ai_calls: list[dict] = []
    warnings: list[str] = []

    on_stage("extract")
    full_text, extract_warnings, sources = extract.extract_files(files, llm=llm, calls=ai_calls)
    warnings.extend(extract_warnings)
    if not full_text.strip():
        raise AIError("nothing_to_summarize", {"detail": "no extractable text in the given files"})

    on_stage("chunk")
    chunks = chunk_text(full_text)

    on_stage("map")
    notes: list[str] = []
    for i, ch in enumerate(chunks, 1):
        _progress(i - 1, len(chunks))
        notes.append(
            str(
                llm.chat(
                    "FAST",
                    [
                        {"role": "system", "content": prompts.MAP_PROMPT.format(language=lang)},
                        {"role": "user", "content": f"Chunk {i} of {len(chunks)}:\n\n{ch}"},
                    ],
                    feature="map",
                    calls=ai_calls,
                )
            )
        )
    _progress(len(chunks), len(chunks))

    on_stage("reduce")
    content_md = str(
        llm.chat(
            "REASON",
            [
                {"role": "system", "content": prompts.reduce_prompt(style, lang, user_note or None)},
                {"role": "user", "content": "Notes per chunk:\n\n" + "\n\n".join(notes)},
            ],
            feature="reduce",
            calls=ai_calls,
        )
    ).strip()

    on_stage("check")
    content_md, still_broken = _format_check(content_md, llm=llm, calls=ai_calls, lang=lang)
    if still_broken:
        # BUG-01: never surface raw technical text; the UI maps this code.
        warnings.append("format_check_failed")

    on_stage("deadlines")
    deadlines: list[dict] = []
    if include_deadlines:
        today = dt.datetime.now(WIB).date()
        try:
            raw = llm.chat(
                "CHECK",
                [
                    {
                        "role": "system",
                        "content": prompts.deadlines_prompt(lang, today.isoformat(), user_note or None),
                    },
                    {"role": "user", "content": content_md[:20000]},
                ],
                json_schema=_DEADLINE_SCHEMA,
                feature="deadlines",
                calls=ai_calls,
                temperature=0.0,  # BUG-01: deterministic extraction
            )
            deadlines, deadline_warnings = _clean_deadlines(raw, today)
            warnings.extend(deadline_warnings)
        except AIError as exc:
            log.warning("deadlines JSON unreadable (%s); trying the dates section fallback", exc.params.get("detail", ""))
        # BUG-01 fallback: parse the "Tanggal & tenggat" section of the summary.
        if not deadlines:
            deadlines = fallback_deadlines(content_md, today)
            if not deadlines:
                warnings.append("deadlines_unreadable")

    return {
        "content_md": content_md,
        "figures": [],
        "sources": sources,
        "deadlines": deadlines,
        "warnings": warnings,
        "warning": still_broken,
        "ai_calls": ai_calls,
    }


__all__ = ["CHUNK_TARGET", "KINDS", "STAGES", "SUBKINDS", "chunk_text", "fallback_deadlines", "summarize"]
