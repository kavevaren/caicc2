"""Subjects router (SPEC §6): list (with followed flag) and create-or-reuse."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from server.api.deps import get_current_user
from server.api.errors import APIError
from server.store import db

router = APIRouter(tags=["Subjects"])


class CreateSubjectRequest(BaseModel):
    name: str


def _subject(row, followed: bool) -> dict:
    return {"id": row["id"], "name": row["name"], "followed": followed}


@router.get("/api/subjects")
def list_subjects(user: dict = Depends(get_current_user)) -> dict:
    rows = db.read(
        "SELECT s.*, (SELECT 1 FROM user_subjects us WHERE us.user_id = ? AND us.subject_id = s.id) AS is_followed"
        " FROM subjects s ORDER BY s.name COLLATE NOCASE",
        (user["id"],),
    )
    return {"items": [_subject(r, bool(r["is_followed"])) for r in rows]}


@router.post("/api/subjects", status_code=201)
def create_subject(body: CreateSubjectRequest, user: dict = Depends(get_current_user)) -> dict:
    name = body.name.strip()
    if not 1 <= len(name) <= 50:
        raise APIError("validation", 422)
    row = db.read_one("SELECT * FROM subjects WHERE name = ?", (name,))
    if row is None:
        cur = db.write("INSERT INTO subjects (name) VALUES (?)", (name,))
        row = db.read_one("SELECT * FROM subjects WHERE id = ?", (cur.lastrowid,))
    db.write("INSERT OR IGNORE INTO user_subjects (user_id, subject_id) VALUES (?, ?)", (user["id"], row["id"]))
    return _subject(row, True)
