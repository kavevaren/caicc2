"""Dashboard router (SPEC §6, §8.2): one call, real data.

Cut blocks (points_ring, top5, me_row, reminders, questions_for_you) are
returned as null/empty so the contract still matches.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends

from server.api.deps import get_current_user
from server.store import db

router = APIRouter(tags=["Dashboard"])


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


@router.get("/api/dashboard")
def get_dashboard(user: dict = Depends(get_current_user)) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    # The week is shown in the user's local week (Asia/Jakarta, UTC+7, no DST):
    # between 00:00 and 07:00 WIB the UTC date is still the previous day.
    today = now.astimezone(dt.timezone(dt.timedelta(hours=7))).date()
    monday = today - dt.timedelta(days=today.weekday())
    week: list[dict] = []
    for i in range(7):  # Monday..Sunday, ISO dates (contract)
        day = (monday + dt.timedelta(days=i)).isoformat()
        rows = db.read(
            "SELECT * FROM events WHERE user_id = ? AND date(start_at, '+7 hours') = ? ORDER BY start_at",
            (user["id"], day),
        )
        week.append({"date": day, "events": [_event(dict(r)) for r in rows]})

    next_row = db.read_one(
        "SELECT * FROM events WHERE user_id = ? AND start_at > ? ORDER BY start_at LIMIT 1",
        # Same shape as the DB defaults: seconds + 3-digit milliseconds, 'Z'.
        (user["id"], f"{now:%Y-%m-%dT%H:%M:%S}.{now.microsecond // 1000:03d}Z"),
    )

    n_summaries = db.read_one("SELECT count(*) AS n FROM documents WHERE user_id = ? AND kind = 'summary'", (user["id"],))["n"]
    n_transcripts = db.read_one("SELECT count(*) AS n FROM documents WHERE user_id = ? AND kind = 'transcript'", (user["id"],))["n"]
    recent = db.read(
        "SELECT d.id, d.kind, d.title, s.name AS subject_name, d.created_at FROM documents d"
        " LEFT JOIN subjects s ON s.id = d.subject_id WHERE d.user_id = ? ORDER BY d.created_at DESC, d.id DESC LIMIT 5",
        (user["id"],),
    )

    return {
        "week": week,
        "next_event": _event(dict(next_row)) if next_row is not None else None,
        "stats": {
            "summaries": int(n_summaries),
            "transcripts": int(n_transcripts),
            "my_unanswered": 0,
            "points": 0,
            "rank": 1,
        },
        "points_ring": None,
        "questions_for_you": [],
        "reminders": [],
        "top5": [],
        "me_row": None,
        "recent": [
            {"id": r["id"], "kind": r["kind"], "title": r["title"], "subject": r["subject_name"], "created_at": r["created_at"]}
            for r in recent
        ],
    }
