"""F4 router (SPEC §6): forum (L6 core).

Implemented: list (FTS5), create, get with answers, owner-only PATCH/DELETE
(soft), answers create + owner-only PATCH/DELETE.
Still 501 (cut): similar, tags, best, follow, votes, hint.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Query, Response
from pydantic import BaseModel

from server.api.deps import get_current_user
from server.api.errors import APIError, not_implemented
from server.store import db

router = APIRouter(tags=["Forum (F4)"])

PAGE_SIZE = 20


def _author(user_id: int) -> dict:
    row = db.read_one("SELECT username, display_name FROM users WHERE id = ?", (user_id,))
    return {"username": row["username"], "display_name": row["display_name"]}


def _excerpt(body_md: str | None) -> str | None:
    if not body_md:
        return None
    text = " ".join(body_md.split())
    return text[:160] + ("…" if len(text) > 160 else "")


def _answers_count(question_id: int) -> int:
    row = db.read_one(
        "SELECT COUNT(*) AS n FROM answers WHERE question_id = ? AND deleted = 0", (question_id,)
    )
    return int(row["n"])


def _question(row) -> dict:
    subject = (
        db.read_one("SELECT name FROM subjects WHERE id = ?", (row["subject_id"],))["name"]
        if row["subject_id"] is not None
        else ""
    )
    tags = [r["tag"] for r in db.read("SELECT tag FROM question_tags WHERE question_id = ? ORDER BY tag", (row["id"],))]
    return {
        "id": row["id"],
        "title": row["title"],
        "body_md": row["body_md"],
        "subject": subject,
        "subject_id": row["subject_id"],
        "tags": tags,
        "author": _author(row["user_id"]),
        "status": row["status"],
        "best_answer_id": None,  # best answer is cut (501)
        "answers_count": _answers_count(row["id"]),
        "score": 0,  # votes are cut (501)
        "excerpt": _excerpt(row["body_md"]),
        "has_attachment": False,  # attachments are cut (501)
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _answer(row) -> dict:
    return {
        "id": row["id"],
        "body_md": row["body_md"],
        "author": _author(row["user_id"]),
        "score": 0,  # votes are cut (501)
        "is_best": False,  # best answer is cut (501)
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "attachments": [],  # attachments are cut (501)
    }


def _get_live_question(question_id: int, user_id: int | None = None) -> dict:
    """Fetch a non-deleted question; 404 for missing, deleted, or (with user_id) foreign."""
    row = db.read_one("SELECT * FROM questions WHERE id = ? AND deleted = 0", (question_id,))
    if row is None or (user_id is not None and row["user_id"] != user_id):
        raise APIError("not_found", 404)
    return row


def _fts_match(q: str) -> str | None:
    """Sanitize a user query into a safe FTS5 expression (quoted phrase per token).

    Tokens without alphanumerics (e.g. '""', '--') are dropped: FTS5 rejects
    empty quoted phrases. Returns None when nothing searchable remains.
    """
    tokens = [t for t in q.split() if any(c.isalnum() for c in t)]
    return " ".join('"' + t.replace('"', "") + '"' for t in tokens) or None


@router.get("/api/questions")
def list_questions(
    q: str | None = Query(default=None, max_length=100),
    status: str = Query(default="all"),
    sort: str = Query(default="newest"),
    subject: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    user: dict = Depends(get_current_user),
) -> object:
    if sort == "most_voted":
        return not_implemented()  # votes are cut
    if status == "followed":
        return not_implemented()  # follow is cut
    where = ["q.deleted = 0"]
    params: list = []
    if q:
        match = _fts_match(q)
        if match is not None:
            where.append("q.id IN (SELECT rowid FROM questions_fts WHERE questions_fts MATCH ?)")
            params.append(match)
    if subject is not None:
        where.append("q.subject_id = ?")
        params.append(subject)
    if status == "open":
        where.append("q.status = 'open'")
    elif status == "answered":
        where.append("q.status = 'answered'")
    sql_where = " AND ".join(where)
    total = int(db.read_one(f"SELECT COUNT(*) AS n FROM questions q WHERE {sql_where}", tuple(params))["n"])
    order = (
        "(SELECT COUNT(*) FROM answers a WHERE a.question_id = q.id AND a.deleted = 0) ASC, q.created_at DESC"
        if sort == "unanswered"
        else "q.created_at DESC"
    )
    rows = db.read(
        f"SELECT q.* FROM questions q WHERE {sql_where} ORDER BY {order} LIMIT ? OFFSET ?",
        (*params, PAGE_SIZE, (page - 1) * PAGE_SIZE),
    )
    return {
        "items": [_question(r) for r in rows],
        "total": total,
        "page": page,
        "pages": (total + PAGE_SIZE - 1) // PAGE_SIZE,
    }


@router.post("/api/questions", status_code=201)
def create_question(
    title: str = Form(),
    body_md: str = Form(default=""),
    subject_id: int = Form(),
    user: dict = Depends(get_current_user),
) -> dict:
    title = title.strip()
    if not 10 <= len(title) <= 150:
        raise APIError("title_length", 422)
    if len(body_md) > 10000:
        raise APIError("validation", 422)
    if db.read_one("SELECT id FROM subjects WHERE id = ?", (subject_id,)) is None:
        raise APIError("validation", 422)
    cur = db.write(
        "INSERT INTO questions (user_id, subject_id, title, body_md, status) VALUES (?, ?, ?, ?, 'open')",
        (user["id"], subject_id, title, body_md.strip() or None),
    )
    return _question(db.read_one("SELECT * FROM questions WHERE id = ?", (cur.lastrowid,)))


@router.post("/api/questions/similar")
def similar_questions(user: dict = Depends(get_current_user)) -> object:
    return not_implemented()


@router.post("/api/questions/tags")
def suggest_tags(user: dict = Depends(get_current_user)) -> object:
    return not_implemented()


@router.get("/api/questions/{question_id}")
def get_question(question_id: int, user: dict = Depends(get_current_user)) -> dict:
    row = db.read_one("SELECT * FROM questions WHERE id = ? AND deleted = 0", (question_id,))
    if row is None:
        raise APIError("not_found", 404)
    detail = _question(row)
    answers = db.read(
        "SELECT * FROM answers WHERE question_id = ? AND deleted = 0 ORDER BY created_at ASC", (question_id,)
    )
    detail["answers"] = [_answer(a) for a in answers]
    return detail


class PatchQuestionBody(BaseModel):
    title: str | None = None
    body_md: str | None = None
    subject_id: int | None = None


@router.patch("/api/questions/{question_id}")
def patch_question(question_id: int, body: PatchQuestionBody, user: dict = Depends(get_current_user)) -> dict:
    _get_live_question(question_id, user["id"])
    sets: list[str] = []
    params: list = []
    if body.title is not None:
        title = body.title.strip()
        if not 10 <= len(title) <= 150:
            raise APIError("title_length", 422)
        sets.append("title = ?")
        params.append(title)
    if body.body_md is not None:
        if len(body.body_md) > 10000:
            raise APIError("validation", 422)
        sets.append("body_md = ?")
        params.append(body.body_md.strip() or None)
    if body.subject_id is not None:
        if db.read_one("SELECT id FROM subjects WHERE id = ?", (body.subject_id,)) is None:
            raise APIError("validation", 422)
        sets.append("subject_id = ?")
        params.append(body.subject_id)
    if not sets:
        raise APIError("validation", 422)
    sets.append("updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')")
    db.write(f"UPDATE questions SET {', '.join(sets)} WHERE id = ?", (*params, question_id))
    return _question(db.read_one("SELECT * FROM questions WHERE id = ?", (question_id,)))


@router.delete("/api/questions/{question_id}", status_code=204)
def delete_question(question_id: int, user: dict = Depends(get_current_user)) -> Response:
    _get_live_question(question_id, user["id"])
    db.write("UPDATE questions SET deleted = 1 WHERE id = ?", (question_id,))
    return Response(status_code=204)


@router.post("/api/questions/{question_id}/answers", status_code=201)
def create_answer(
    question_id: int,
    body_md: str = Form(),
    user: dict = Depends(get_current_user),
) -> dict:
    if len(body_md) > 10000:
        raise APIError("validation", 422)
    if not body_md.strip():
        raise APIError("validation", 422)
    row = db.read_one("SELECT * FROM questions WHERE id = ? AND deleted = 0", (question_id,))
    if row is None:
        raise APIError("not_found", 404)
    cur = db.write(
        "INSERT INTO answers (question_id, user_id, body_md) VALUES (?, ?, ?)",
        (question_id, user["id"], body_md.strip()),
    )
    db.write("UPDATE questions SET status = 'answered' WHERE id = ? AND status = 'open'", (question_id,))
    return _answer(db.read_one("SELECT * FROM answers WHERE id = ?", (cur.lastrowid,)))


class PatchAnswerBody(BaseModel):
    body_md: str


@router.patch("/api/answers/{answer_id}")
def patch_answer(answer_id: int, body: PatchAnswerBody, user: dict = Depends(get_current_user)) -> dict:
    if len(body.body_md) > 10000 or not body.body_md.strip():
        raise APIError("validation", 422)
    row = db.read_one("SELECT * FROM answers WHERE id = ? AND deleted = 0", (answer_id,))
    if row is None or row["user_id"] != user["id"]:
        raise APIError("not_found", 404)
    db.write(
        "UPDATE answers SET body_md = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
        (body.body_md.strip(), answer_id),
    )
    return _answer(db.read_one("SELECT * FROM answers WHERE id = ?", (answer_id,)))


@router.delete("/api/answers/{answer_id}", status_code=204)
def delete_answer(answer_id: int, user: dict = Depends(get_current_user)) -> Response:
    row = db.read_one("SELECT * FROM answers WHERE id = ? AND deleted = 0", (answer_id,))
    if row is None or row["user_id"] != user["id"]:
        raise APIError("not_found", 404)
    db.write("UPDATE answers SET deleted = 1 WHERE id = ?", (answer_id,))
    if _answers_count(row["question_id"]) == 0:
        db.write("UPDATE questions SET status = 'open' WHERE id = ? AND status = 'answered'", (row["question_id"],))
    return Response(status_code=204)


@router.post("/api/questions/{question_id}/best")
def mark_best_answer(question_id: int, user: dict = Depends(get_current_user)) -> object:
    return not_implemented()


@router.post("/api/questions/{question_id}/follow")
def follow_question(question_id: int, user: dict = Depends(get_current_user)) -> object:
    return not_implemented()


@router.post("/api/questions/{question_id}/hint")
def request_hint(question_id: int, user: dict = Depends(get_current_user)) -> object:
    return not_implemented()


@router.post("/api/votes")
def vote(user: dict = Depends(get_current_user)) -> object:
    return not_implemented()
