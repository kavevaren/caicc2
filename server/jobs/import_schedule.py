"""Schedule import (L7 task 2 + QA fixes).

ICS files are parsed in Python (no AI). Any other file goes through
server.ai.extract, then ONE CHECK call with the import schema. XLSX is read
as plain text rows by extract.py (stdlib only). Dates are resolved to
Asia/Jakarta (WIB); anything unresolvable is dropped, never invented.

BUG-03: parse_ics keeps the VEVENT UID (+RECURRENCE-ID) so the runner can
upsert instead of duplicating on re-import. FEAT-01: `notes` filters the
deterministic ICS parse (no AI) and steers the AI extraction.

Returns (suggestions, ai_calls): each suggestion is {title, kind, subkind,
start_at, end_at, location, evidence, ics_uid?} with stored-format datetimes
(UTC ISO SS.mmmZ).
"""
from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable
from typing import Any

from server.ai import prompts
from server.ai.errors import AIError

WIB = dt.timezone(dt.timedelta(hours=7))
KINDS = ("kelas", "belajar", "acara", "tenggat")
SUBKINDS = ("tugas", "kuis", "ujian")
IMPORT_TEXT_CAP = 24_000

IMPORT_SCHEMA: dict = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "kind": {"type": "string"},
            "subkind": {"type": ["string", "null"]},
            "start_at": {"type": "string"},
            "end_at": {"type": ["string", "null"]},
            "location": {"type": ["string", "null"]},
        },
        "required": ["title", "kind", "start_at"],
    },
}


def _default_llm() -> Any:
    from server.ai import llm

    return llm


def _fmt(d: dt.datetime) -> str:
    d = d.astimezone(dt.timezone.utc)
    return f"{d.strftime('%Y-%m-%dT%H:%M:%S')}.{d.microsecond // 1000:03d}Z"


def _try_wib(value: str | None) -> dt.datetime | None:
    """Naive input is WIB, aware input is converted; None when unresolvable."""
    if not value:
        return None
    v = str(value).strip()
    try:
        if "T" not in v:
            return dt.datetime.combine(dt.date.fromisoformat(v[:10]), dt.time.min, tzinfo=WIB).astimezone(dt.timezone.utc)
        d = dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=WIB)
        return d.astimezone(dt.timezone.utc)
    except ValueError:
        return None


# ---------------------------------------------------------------- ICS (no AI)

# FEAT-01: the user note may filter the deterministic ICS parse. We extract
# inclusion terms (positive clauses) and exclusion terms (clauses starting
# with a negation word). If the inclusion filter would drop everything, we
# keep all events (the note was probably categorization, not a filter).
_NEGATION = ("abaikan", "lewatkan", "jangan", "skip", "exclude", "hilangkan", "skip", "tanpa")
_STOP = {"dan", "yang", "dengan", "di", "ke", "dari", "hanya", "semua", "atau", "masuk",
         "jenis", "the", "only", "and", "with", "from", "into", "all", "ignore"}


def _note_terms(notes: str) -> tuple[set[str], set[str]]:
    include: set[str] = set()
    exclude: set[str] = set()
    for clause in re.split(r"[;.,]\s*|\s\s+", notes):
        words = re.findall(r"[a-z]{3,}", clause.lower())
        target = exclude if words and words[0] in _NEGATION else include
        target.update(w for w in words if w not in _STOP)
    return include, exclude


def filter_ics(items: list[dict], notes: str | None) -> list[dict]:
    n = (notes or "").strip()
    if not n:
        return items
    include, exclude = _note_terms(n)
    def _keep(it: dict) -> bool:
        hay = f"{it.get('title', '')} {it.get('location') or ''}".lower()
        if exclude and any(w in hay for w in exclude):
            return False
        if include:
            return any(w in hay for w in include)
        return True
    kept = [it for it in items if _keep(it)]
    return kept if kept else items  # safety valve: never filter to empty


# ---------------------------------------------------------------- ICS (no AI)

def _ics_date(value: str) -> dt.datetime | None:
    v = value.strip().upper()
    if re.fullmatch(r"\d{8}T\d{6}Z", v):
        return dt.datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
    if re.fullmatch(r"\d{8}T\d{6}", v):
        return dt.datetime.strptime(v, "%Y%m%dT%H%M%S").replace(tzinfo=WIB)
    if re.fullmatch(r"\d{8}", v):
        return dt.datetime.strptime(v, "%Y%m%d").replace(tzinfo=WIB)
    return None


def _ics_unescape(text: str) -> str:
    return re.sub(r"\\([,;nN])", lambda m: "\n" if m.group(1).lower() == "n" else m.group(1), text)


def parse_ics(text: str) -> list[dict]:
    """RFC 5545 VEVENTs -> [{title, kind, start_at, end_at?, location?,
    ics_uid?}] (WIB-aware). BUG-03: keeps UID (+RECURRENCE-ID) for dedup."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded: list[str] = []
    for line in lines:  # unfolding: continuation lines start with a space
        if line[:1] in (" ", "\t") and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    items: list[dict] = []
    cur: dict[str, str] = {}
    for line in unfolded:
        if line.startswith("BEGIN:VEVENT"):
            cur = {}
        elif line.startswith("END:VEVENT"):
            if cur.get("SUMMARY"):
                start = _ics_date(cur.get("DTSTART", ""))
                if start is not None:
                    item: dict[str, Any] = {
                        "title": _ics_unescape(cur["SUMMARY"]).strip()[:150],
                        "kind": "acara",
                        "start_at": _fmt(start),
                    }
                    end = _ics_date(cur.get("DTEND", "")) if cur.get("DTEND") else None
                    if end is not None and end > start:
                        item["end_at"] = _fmt(end)
                    if cur.get("LOCATION", "").strip():
                        item["location"] = _ics_unescape(cur["LOCATION"]).strip()[:150]
                    if cur.get("UID", "").strip():
                        uid = cur["UID"].strip()
                        if cur.get("RECURRENCE-ID", "").strip():
                            uid = f"{uid}:{cur['RECURRENCE-ID'].strip()}"
                        item["ics_uid"] = uid[:200]
                    items.append(item)
            cur = {}
        elif ":" in line:
            key, _, val = line.partition(":")
            key = key.split(";")[0].upper()
            if key in ("SUMMARY", "DTSTART", "DTEND", "LOCATION", "UID", "RECURRENCE-ID"):
                cur[key] = val.strip()
    return items


# ---------------------------------------------------------------- pipeline

def run_import(
    files: list[dict],
    on_stage: Callable[[str], None] | None = None,
    *,
    llm: Any = None,
    notes: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """files: [{path, name, ext, ...}] as saved by the import endpoint.

    FEAT-01: `notes` (max 500 chars) filters the ICS parse deterministically
    and is injected into the AI prompt as a selection instruction only."""
    if llm is None:
        llm = _default_llm()
    stage = on_stage or (lambda _s: None)
    calls: list[dict] = []
    raw: list[dict] = []

    ics_files = [f for f in files if f.get("ext") == ".ics"]
    other = [f for f in files if f.get("ext") != ".ics"]

    stage("extract")
    for f in ics_files:
        name = f.get("name") or "file.ics"
        try:
            with open(f["path"], encoding="utf-8", errors="replace") as fh:
                items = parse_ics(fh.read())
                for it in filter_ics(items, notes):  # FEAT-01 deterministic filter
                    it["evidence"] = name
                    raw.append(it)
        except OSError as exc:
            raise AIError("extract_failed", {"name": name, "detail": str(exc)[:200]}) from exc

    text = ""
    if other:
        from server.ai import extract

        text, _, _ = extract.extract_files(other, llm=llm, calls=calls)

    if text.strip():
        stage("check")
        today = dt.datetime.now(WIB).date().isoformat()
        prompt = prompts.schedule_import_prompt("id", today, notes or None)
        data = llm.chat(
            "CHECK",
            [{"role": "user", "content": f"{prompt}\n\n---\n{text[:IMPORT_TEXT_CAP]}"}],
            json_schema=IMPORT_SCHEMA,
            feature="schedule_import",
            calls=calls,
        )
        name = (other or [{}])[0].get("name", "file")
        for d in data or []:
            if isinstance(d, dict):
                d = dict(d)
                d.setdefault("evidence", name)
                raw.append(d)

    if not raw:
        raise AIError("nothing_to_summarize", {})

    # Resolve to WIB, drop what cannot be resolved (never invent dates).
    out: list[dict] = []
    for it in raw:
        title = str(it.get("title") or "").strip()[:150]
        start = _try_wib(it.get("start_at"))
        if not title or start is None:
            continue
        end = _try_wib(it.get("end_at"))
        if end is None or end <= start:
            end = start + dt.timedelta(hours=1)
        kind = it.get("kind")
        kind = kind if kind in KINDS else "acara"
        subkind = it.get("subkind") if kind == "tenggat" and it.get("subkind") in SUBKINDS else None
        item: dict[str, Any] = {
            "title": title,
            "kind": kind,
            "subkind": subkind,
            "start_at": _fmt(start),
            "end_at": _fmt(end),
            "location": (str(it["location"]).strip()[:150] or None) if it.get("location") else None,
            "evidence": str(it.get("evidence") or "")[:500],
        }
        if it.get("ics_uid"):
            item["ics_uid"] = str(it["ics_uid"])[:200]
        out.append(item)
    if not out:
        raise AIError("nothing_to_summarize", {})
    return out, calls


__all__ = ["IMPORT_SCHEMA", "filter_ics", "parse_ics", "run_import"]
