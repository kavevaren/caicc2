"""F3 router (SPEC §8.5, lean local mode): events CRUD + .ics + suggestions.

Google endpoints stay 501 (cut from the lean scope). Naive datetimes from the
client are interpreted as Asia/Jakarta (UTC+7, no DST) and stored as UTC ISO.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from pydantic import BaseModel, Field

from server.ai.probe import ms_state
from server.api.deps import get_current_user, require_upload_rate
from server.api.errors import APIError, not_implemented
from server.config import settings
from server.jobs import runner
from server.store import db

router = APIRouter(tags=["Schedule (F3)"])

WIB = dt.timezone(dt.timedelta(hours=7))
REMINDERS = (10, 60, 1440)
# QA categories (owner decision 2026-11-03): kelas / belajar / acara /
# tenggat (subkind tugas|kuis|ujian).
KINDS = ("kelas", "belajar", "acara", "tenggat")
SUBKINDS = ("tugas", "kuis", "ujian")
SOURCES = ("manual", "ringkasan", "impor", "google")


class CreateEventRequest(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    start_at: str
    end_at: str | None = None  # defaults to start + 1 h (SPEC §8.5)
    location: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    reminder_minutes: int | None = None
    kind: str = "belajar"  # kelas / belajar / acara / tenggat
    subkind: str | None = None  # tugas / kuis / ujian (only for 'tenggat')


class PatchEventRequest(BaseModel):
    title: str | None = Field(default=None, max_length=150)
    start_at: str | None = None
    end_at: str | None = None
    location: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    reminder_minutes: int | None = None
    kind: str | None = None
    subkind: str | None = None


def _check_kind(kind: str, subkind: str | None) -> None:
    if kind not in KINDS:
        raise APIError("validation", 422)
    if subkind is not None and (kind != "tenggat" or subkind not in SUBKINDS):
        raise APIError("validation", 422)


def _parse_dt(value: str) -> dt.datetime:
    """Client input: ISO datetime (naive = WIB) or date-only (midnight WIB)."""
    v = value.strip()
    try:
        if "T" not in v:
            d = dt.datetime.combine(dt.date.fromisoformat(v[:10]), dt.time.min, tzinfo=WIB)
        else:
            d = dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=WIB)
    except (ValueError, AttributeError):
        raise APIError("validation", 422) from None
    return d.astimezone(dt.timezone.utc)


def _stored_dt(value: str) -> dt.datetime:
    """Stored values: date-only (suggestions, midnight WIB) or UTC ISO with an
    optional fraction (3- or 6-digit, dotted or not)."""
    v = value.strip()
    try:
        if "T" not in v:
            return dt.datetime.combine(dt.date.fromisoformat(v[:10]), dt.time.min, tzinfo=WIB)
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.?(\d{1,6}))?\+00:00", v.replace("Z", "+00:00"))
        if not m:
            raise ValueError(v)
        d = dt.datetime.fromisoformat(m.group(1))
        if m.group(2):
            d = d.replace(microsecond=int(m.group(2).ljust(6, "0")))
        return d.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        raise APIError("validation", 422) from None


def _fmt(d: dt.datetime) -> str:
    # Same shape as the DB default: strftime('%Y-%m-%dT%H:%M:%fZ') -> SS.mmmZ.
    d = d.astimezone(dt.timezone.utc)
    return f"{d.strftime('%Y-%m-%dT%H:%M:%S')}.{d.microsecond // 1000:03d}Z"


def _event(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "start_at": row["start_at"],
        "end_at": row["end_at"],
        "location": row["location"],
        "description": row["description"],
        "reminder_minutes": row["reminder_minutes"],
        "source": row["source"],
        "kind": row["kind"],
        "subkind": row["subkind"],
        "google_event_id": row["google_event_id"],
        "created_at": row["created_at"],
    }


def _suggestion(row: dict) -> dict:
    return {
        "id": row["id"],
        "document_id": row["document_id"],
        "title": row["title"],
        "start_at": row["start_at"],
        "end_at": row["end_at"],
        "location": row["location"],
        "evidence": row["evidence"],
        "status": row["status"],
        "kind": row["kind"],
        "subkind": row["subkind"],
        "source": row["source"],
    }


def _check_range(start: dt.datetime, end: dt.datetime) -> None:
    if end <= start:
        raise APIError("end_before_start", 422)


def _check_reminder(reminder: int | None) -> None:
    if reminder is not None and reminder not in REMINDERS:
        raise APIError("validation", 422)


@router.get("/api/events")
def list_events(
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    # Default: today (WIB) to +30 days (contract summary).
    today = dt.datetime.now(WIB).date()
    try:
        d_from = dt.date.fromisoformat(from_) if from_ else today
        d_to = dt.date.fromisoformat(to) if to else d_from + dt.timedelta(days=30)
    except ValueError:
        raise APIError("validation", 422) from None
    lo = _fmt(dt.datetime.combine(d_from, dt.time.min, tzinfo=WIB))
    hi = _fmt(dt.datetime.combine(d_to, dt.time.max, tzinfo=WIB))
    rows = db.read(
        "SELECT * FROM events WHERE user_id = ? AND start_at >= ? AND start_at <= ? ORDER BY start_at",
        (user["id"], lo, hi),
    )
    return {"items": [_event(r) for r in rows]}


@router.post("/api/events", status_code=201)
def create_event(body: CreateEventRequest, user: dict = Depends(get_current_user)) -> dict:
    title = body.title.strip()
    if not title:
        raise APIError("validation", 422)
    start = _parse_dt(body.start_at)
    end = _parse_dt(body.end_at) if body.end_at else start + dt.timedelta(hours=1)
    _check_range(start, end)
    _check_reminder(body.reminder_minutes)
    _check_kind(body.kind, body.subkind)
    cur = db.write(
        "INSERT INTO events (user_id, title, start_at, end_at, location, description, reminder_minutes, source, kind, subkind)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?)",
        (user["id"], title, _fmt(start), _fmt(end), body.location, body.description, body.reminder_minutes, body.kind, body.subkind),
    )
    row = db.read_one("SELECT * FROM events WHERE id = ?", (cur.lastrowid,))
    return _event(row)


@router.patch("/api/events/{event_id}")
def patch_event(event_id: int, body: PatchEventRequest, user: dict = Depends(get_current_user)) -> dict:
    row = db.read_one("SELECT * FROM events WHERE id = ? AND user_id = ?", (event_id, user["id"]))
    if row is None:
        raise APIError("not_found", 404)
    start = _parse_dt(body.start_at) if body.start_at else _stored_dt(row["start_at"])
    end = _parse_dt(body.end_at) if body.end_at else _stored_dt(row["end_at"])
    _check_range(start, end)
    _check_reminder(body.reminder_minutes)
    title = body.title.strip() if body.title is not None else row["title"]
    if not title:
        raise APIError("validation", 422)
    location = body.location if body.location is not None else row["location"]
    description = body.description if body.description is not None else row["description"]
    reminder = body.reminder_minutes if body.reminder_minutes is not None else row["reminder_minutes"]
    kind = body.kind if body.kind is not None else row["kind"]
    subkind = body.subkind if body.subkind is not None else row["subkind"]
    if kind == "tenggat" and subkind not in (None, *SUBKINDS):
        raise APIError("validation", 422)
    if kind != "tenggat":
        subkind = None
    db.write(
        "UPDATE events SET title = ?, start_at = ?, end_at = ?, location = ?, description = ?, reminder_minutes = ?, kind = ?, subkind = ?"
        " WHERE id = ?",
        (title, _fmt(start), _fmt(end), location, description, reminder, kind, subkind, event_id),
    )
    row = db.read_one("SELECT * FROM events WHERE id = ?", (event_id,))
    return _event(row)


@router.delete("/api/events/{event_id}", status_code=204)
def delete_event(event_id: int, user: dict = Depends(get_current_user)) -> Response:
    cur = db.write("DELETE FROM events WHERE id = ? AND user_id = ?", (event_id, user["id"]))
    if cur.rowcount == 0:
        raise APIError("not_found", 404)
    return Response(status_code=204)


def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


@router.get("/api/events/{event_id}.ics")
def event_ics(event_id: int, user: dict = Depends(get_current_user)) -> Response:
    row = db.read_one("SELECT * FROM events WHERE id = ? AND user_id = ?", (event_id, user["id"]))
    if row is None:
        raise APIError("not_found", 404)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fmt = "%Y%m%dT%H%M%SZ"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Orvina//CAICC 2026//ID",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{row['ics_uid'] or f'{uuid.uuid4()}@orvina'}",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{_stored_dt(row['start_at']).astimezone(dt.timezone.utc).strftime(fmt)}",
        f"DTEND:{_stored_dt(row['end_at']).astimezone(dt.timezone.utc).strftime(fmt)}",
        f"SUMMARY:{_ics_escape(row['title'])}",
    ]
    if row["location"]:
        lines.append(f"LOCATION:{_ics_escape(row['location'])}")
    if row["description"]:
        lines.append(f"DESCRIPTION:{_ics_escape(row['description'])}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    body = "\r\n".join(lines) + "\r\n"
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="event-{event_id}.ics"'},
    )


@router.get("/api/suggestions")
def list_suggestions(user: dict = Depends(get_current_user)) -> dict:
    rows = db.read(
        "SELECT * FROM event_suggestions WHERE user_id = ? AND status = 'pending' ORDER BY start_at",
        (user["id"],),
    )
    return {"items": [_suggestion(r) for r in rows]}


@router.post("/api/suggestions/{suggestion_id}/accept", status_code=201)
def accept_suggestion(suggestion_id: int, user: dict = Depends(get_current_user)) -> dict:
    s = db.read_one("SELECT * FROM event_suggestions WHERE id = ? AND user_id = ?", (suggestion_id, user["id"]))
    if s is None or s["status"] != "pending":
        raise APIError("not_found", 404)
    start = _stored_dt(s["start_at"])
    end = _stored_dt(s["end_at"]) if s["end_at"] else start + dt.timedelta(hours=1)
    if end <= start:
        end = start + dt.timedelta(hours=1)
    kind = s["kind"] if s["kind"] in KINDS else "belajar"
    subkind = s["subkind"] if kind == "tenggat" and s["subkind"] in SUBKINDS else None
    # BUG-04: the event keeps the suggestion's real source (ringkasan/impor).
    source = s["source"] if s["source"] in SOURCES else "ringkasan"
    event_id: int | None = None
    if s["ics_uid"]:
        # BUG-03: accept never duplicates an imported VEVENT (upsert).
        existing = db.read_one("SELECT id FROM events WHERE user_id = ? AND ics_uid = ?", (user["id"], s["ics_uid"]))
        if existing:
            db.write(
                "UPDATE events SET title = ?, start_at = ?, end_at = ?, location = ?, description = ?, source = ?, kind = ?, subkind = ?"
                " WHERE id = ?",
                (s["title"], _fmt(start), _fmt(end), s["location"], s["evidence"], source, kind, subkind, existing["id"]),
            )
            event_id = int(existing["id"])
    if event_id is None:
        cur = db.write(
            "INSERT INTO events (user_id, title, start_at, end_at, location, description, reminder_minutes, source, kind, subkind, ics_uid)"
            " VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)",
            (user["id"], s["title"], _fmt(start), _fmt(end), s["location"], s["evidence"], source, kind, subkind, s["ics_uid"]),
        )
        event_id = int(cur.lastrowid)
    db.write("UPDATE event_suggestions SET status = 'added' WHERE id = ?", (suggestion_id,))
    row = db.read_one("SELECT * FROM events WHERE id = ?", (event_id,))
    return _event(row)


class SuggestionPatchRequest(BaseModel):
    """FEAT-01: inline edit of a pending suggestion before saving."""

    title: str | None = Field(default=None, min_length=1, max_length=150)
    start_at: str | None = None
    end_at: str | None = None
    location: str | None = Field(default=None, max_length=150)
    kind: str | None = None
    subkind: str | None = None


@router.patch("/api/suggestions/{suggestion_id}")
def patch_suggestion(suggestion_id: int, body: SuggestionPatchRequest, user: dict = Depends(get_current_user)) -> dict:
    s = db.read_one("SELECT * FROM event_suggestions WHERE id = ? AND user_id = ? AND status = 'pending'", (suggestion_id, user["id"]))
    if s is None:
        raise APIError("not_found", 404)
    title = body.title.strip() if body.title is not None else s["title"]
    if not title:
        raise APIError("validation", 422)
    start = _stored_dt(body.start_at) if body.start_at else _stored_dt(s["start_at"])
    end = _stored_dt(body.end_at) if body.end_at else (s["end_at"] and _stored_dt(s["end_at"]))
    if end is not None and end <= start:
        raise APIError("end_before_start", 422)
    location = body.location if body.location is not None else s["location"]
    kind = body.kind if body.kind is not None else s["kind"]
    subkind = body.subkind if body.subkind is not None else s["subkind"]
    if kind not in KINDS:
        raise APIError("validation", 422)
    if subkind is not None and kind != "tenggat":
        subkind = None
    if kind == "tenggat" and subkind not in (None, *SUBKINDS):
        raise APIError("validation", 422)
    db.write(
        "UPDATE event_suggestions SET title = ?, start_at = ?, end_at = ?, location = ?, kind = ?, subkind = ? WHERE id = ?",
        (title, _fmt(start), _fmt(end) if end else None, location, kind, subkind, suggestion_id),
    )
    row = db.read_one("SELECT * FROM event_suggestions WHERE id = ?", (suggestion_id,))
    return _suggestion(row)


class SuggestionBatchRequest(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=100)


@router.post("/api/suggestions/accept-batch", status_code=201)
def accept_suggestions_batch(body: SuggestionBatchRequest, user: dict = Depends(get_current_user)) -> dict:
    """FEAT-01: 'Tambahkan ke kalender' for the checked preview items."""
    items: list[dict] = []
    for sid in body.ids:
        try:
            items.append(accept_suggestion(sid, user))
        except APIError as exc:
            if exc.status == 404:
                continue
            raise
    return {"items": items}


@router.post("/api/suggestions/dismiss-batch", status_code=204)
def dismiss_suggestions_batch(body: SuggestionBatchRequest, user: dict = Depends(get_current_user)) -> Response:
    db.write(
        "UPDATE event_suggestions SET status = 'dismissed' WHERE user_id = ? AND status = 'pending' AND id IN ("
        + ",".join("?" * len(body.ids))
        + ")",
        (user["id"], *body.ids),
    )
    return Response(status_code=204)


@router.post("/api/suggestions/{suggestion_id}/dismiss", status_code=204)
def dismiss_suggestion(suggestion_id: int, user: dict = Depends(get_current_user)) -> Response:
    cur = db.write(
        "UPDATE event_suggestions SET status = 'dismissed' WHERE id = ? AND user_id = ? AND status = 'pending'",
        (suggestion_id, user["id"]),
    )
    if cur.rowcount == 0:
        raise APIError("not_found", 404)
    return Response(status_code=204)


class TodoRequest(BaseModel):
    title: str = Field(default="", max_length=150)
    done: bool | None = None
    due_date: str | None = None  # YYYY-MM-DD (WIB day) or null


def _todo(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"]),
        "due_date": row["due_date"],
        "created_at": row["created_at"],
    }


def _check_due(due: str) -> None:
    try:
        dt.date.fromisoformat(due)
    except ValueError:
        raise APIError("validation", 422) from None


@router.get("/api/todos")
def list_todos(user: dict = Depends(get_current_user)) -> dict:
    rows = db.read(
        "SELECT * FROM todos WHERE user_id = ? ORDER BY done ASC, created_at DESC, id DESC",
        (user["id"],),
    )
    return {"items": [_todo(r) for r in rows]}


@router.post("/api/todos", status_code=201)
def create_todo(body: TodoRequest, user: dict = Depends(get_current_user)) -> dict:
    title = body.title.strip()
    if not title:
        raise APIError("validation", 422)
    if body.due_date:
        _check_due(body.due_date)
    cur = db.write(
        "INSERT INTO todos (user_id, title, done, due_date, created_at)"
        " VALUES (?, ?, 0, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
        (user["id"], title, body.due_date),
    )
    row = db.read_one("SELECT * FROM todos WHERE id = ?", (cur.lastrowid,))
    return _todo(row)


@router.patch("/api/todos/{todo_id}")
def patch_todo(todo_id: int, body: TodoRequest, user: dict = Depends(get_current_user)) -> dict:
    row = db.read_one("SELECT * FROM todos WHERE id = ? AND user_id = ?", (todo_id, user["id"]))
    if row is None:
        raise APIError("not_found", 404)
    title = body.title.strip() if body.title else row["title"]
    if not title:
        raise APIError("validation", 422)
    done = 1 if body.done is True else 0 if body.done is False else row["done"]
    due = body.due_date if body.due_date is not None else row["due_date"]
    if body.due_date:
        _check_due(body.due_date)
    db.write(
        "UPDATE todos SET title = ?, done = ?, due_date = ? WHERE id = ?",
        (title, done, due, todo_id),
    )
    row = db.read_one("SELECT * FROM todos WHERE id = ?", (todo_id,))
    return _todo(row)


@router.delete("/api/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int, user: dict = Depends(get_current_user)) -> Response:
    cur = db.write("DELETE FROM todos WHERE id = ? AND user_id = ?", (todo_id, user["id"]))
    if cur.rowcount == 0:
        raise APIError("not_found", 404)
    return Response(status_code=204)


# ---------------------------------------------------------------- schedule import (L7 task 2)

IMPORT_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".docx", ".xlsx", ".ics"}
IMPORT_MAX_FILES = 5


@router.post("/api/schedule/import", status_code=202)
def import_schedule(
    user: dict = Depends(get_current_user),
    files: list[UploadFile] = File(default=[]),
    notes: str | None = Form(default=None),
) -> dict:
    """Multipart import of up to 5 files. ICS is parsed locally (no AI); the
    other formats go through extract + one CHECK call. ICS items land in the
    calendar directly (upsert by UID); AI items surface in the review card.
    FEAT-01: `notes` (max 500) filters ICS items deterministically and steers
    the AI extraction as a selection instruction only."""
    ms = ms_state()["status"]
    if ms == "invalid_token":
        raise APIError("modelscope_token_invalid", 503)
    if ms == "unreachable":
        raise APIError("ai_unavailable", 502)
    if not files:
        raise APIError("validation", 422)
    if len(files) > IMPORT_MAX_FILES:
        raise APIError("validation", 422)
    if notes is not None and len(notes) > 500:
        raise APIError("validation", 422)
    require_upload_rate(user)

    max_bytes = settings.max_upload_mb * 1024 * 1024
    uploads_dir = settings.data_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    saved: list[dict] = []
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in IMPORT_EXTS:
            raise APIError("validation", 422)
        data = f.file.read()
        if len(data) > max_bytes:
            raise APIError("file_too_large", 413)
        stored_name = f"{uuid.uuid4()}{ext}"
        stored_path = uploads_dir / stored_name
        stored_path.write_bytes(data)
        saved.append({"path": str(stored_path), "name": f.filename or stored_name, "ext": ext, "size": len(data)})

    job_id = str(uuid.uuid4())
    db.write(
        "INSERT INTO jobs (id, user_id, kind, status, stage, stages_json, label, notes, created_at, updated_at)"
        " VALUES (?, ?, 'schedule_import', 'queued', 'queued', '[]', ?, ?,"
        " strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
        (job_id, user["id"], (files[0].filename or "impor"), (notes or "").strip()[:500] or None),
    )
    runner.submit_import(job_id, user["id"], saved, (notes or "").strip()[:500] or None)
    return {"job_id": job_id}


@router.get("/api/schedule/import-meta")
def import_meta(user: dict = Depends(get_current_user)) -> dict:
    """FEAT-01: last import notes, for 'Impor ulang dengan catatan yang sama'."""
    row = db.read_one(
        "SELECT notes FROM jobs WHERE user_id = ? AND kind = 'schedule_import' ORDER BY created_at DESC, id DESC LIMIT 1",
        (user["id"],),
    )
    return {"notes": row["notes"] if row else None}


# Google Calendar is cut from the lean scope — keep the contract stubs (501).
@router.get("/api/google/connect")
def google_connect(user: dict = Depends(get_current_user)) -> object:
    return not_implemented()


@router.get("/api/google/callback")
def google_callback(code: str = Query(min_length=1), state: str = Query(min_length=1)) -> object:
    return not_implemented()


@router.delete("/api/google")
def google_disconnect(user: dict = Depends(get_current_user)) -> object:
    return not_implemented()
