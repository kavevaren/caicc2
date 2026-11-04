"""Chat router (L7 task 4, "Tanya"): owner-only AI chats grounded on the
student's own summaries.

One synchronous REASON call per question (the lean scope cuts SSE; the client
shows the AtomLoader while waiting). The context is the documents of the chat's
project, or the user's three most recent summaries when it has no project.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from server.ai import chat_answer
from server.ai.errors import AIError, ModelScopeAuthError
from server.ai.probe import ms_state
from server.api.deps import get_current_user
from server.api.errors import APIError
from server.store import db

router = APIRouter(tags=["Tanya (L7)"])

NO_PROJECT_DOCS = 3  # fallback context when a chat has no project


class CreateChatRequest(BaseModel):
    project_id: int | None = None


class PostMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


def _get_owned(chat_id: int, user: dict) -> dict:
    row = db.read_one(
        "SELECT c.*, p.title AS project_title FROM chats c"
        " LEFT JOIN projects p ON p.id = c.project_id"
        " WHERE c.id = ? AND c.user_id = ?",
        (chat_id, user["id"]),
    )
    if row is None:
        raise APIError("not_found", 404)
    return dict(row)


def _detail(chat_id: int, user: dict) -> dict:
    c = _get_owned(chat_id, user)
    msgs = db.read(
        "SELECT id, role, content_md, created_at FROM chat_messages WHERE chat_id = ? ORDER BY id",
        (chat_id,),
    )
    return {
        "id": c["id"],
        "title": c["title"],
        "project_id": c["project_id"],
        "project_title": c["project_title"],
        "messages": [dict(m) for m in msgs],
        "created_at": c["created_at"],
        "updated_at": c["updated_at"],
    }


def _material(chat: dict, user: dict) -> str:
    """Context: the project's documents in position order, or the user's most
    recent summaries when the chat has no project. Capped per document."""
    per_doc = 8000
    parts: list[str] = []
    if chat["project_id"] is not None:
        rows = db.read(
            "SELECT d.title, d.content_md FROM project_documents pd"
            " JOIN documents d ON d.id = pd.document_id"
            " WHERE pd.project_id = ? AND d.user_id = ? ORDER BY pd.position, pd.added_at",
            (chat["project_id"], user["id"]),
        )
    else:
        rows = db.read(
            "SELECT title, content_md FROM documents WHERE user_id = ? AND kind = 'summary'"
            " ORDER BY created_at DESC LIMIT ?",
            (user["id"], NO_PROJECT_DOCS),
        )
    total = 0
    for r in rows:
        text = r["content_md"][:per_doc]
        parts.append(f"### {r['title']}\n\n{text}")
        total += len(text)
        if total >= chat_answer.MAX_MATERIAL_CHARS:
            break
    return "\n\n".join(parts)


@router.get("/api/chats")
def list_chats(user: dict = Depends(get_current_user)) -> dict:
    rows = db.read(
        "SELECT c.id, c.title, c.project_id, p.title AS project_title, c.updated_at"
        " FROM chats c LEFT JOIN projects p ON p.id = c.project_id"
        " WHERE c.user_id = ? ORDER BY c.updated_at DESC, c.id DESC",
        (user["id"],),
    )
    return {
        "items": [
            {
                "id": r["id"],
                "title": r["title"],
                "project_id": r["project_id"],
                "project_title": r["project_title"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]
    }


@router.post("/api/chats", status_code=201)
def create_chat(body: CreateChatRequest, user: dict = Depends(get_current_user)) -> dict:
    if body.project_id is not None:
        own = db.read_one(
            "SELECT id FROM projects WHERE id = ? AND user_id = ?",
            (body.project_id, user["id"]),
        )
        if own is None:
            raise APIError("not_found", 404)
    cur = db.write(
        "INSERT INTO chats (user_id, title, project_id) VALUES (?, '', ?)",
        (user["id"], body.project_id),
    )
    return _detail(cur.lastrowid, user)


@router.get("/api/chats/{chat_id}")
def get_chat(chat_id: int, user: dict = Depends(get_current_user)) -> dict:
    return _detail(chat_id, user)


@router.delete("/api/chats/{chat_id}", status_code=204)
def delete_chat(chat_id: int, user: dict = Depends(get_current_user)) -> Response:
    _get_owned(chat_id, user)  # 404 if not the owner
    db.write("DELETE FROM chats WHERE id = ? AND user_id = ?", (chat_id, user["id"]))
    return Response(status_code=204)


@router.post("/api/chats/{chat_id}/messages")
def post_message(chat_id: int, body: PostMessageRequest, user: dict = Depends(get_current_user)) -> dict:
    chat = _get_owned(chat_id, user)
    content = body.content.strip()
    if not content:
        raise APIError("validation", 422)

    ms = ms_state()["status"]
    if ms == "invalid_token":
        raise APIError("modelscope_token_invalid", 503)
    if ms == "unreachable":
        raise APIError("ai_unavailable", 502)

    calls: list[dict] = []
    try:
        history = db.read(
            "SELECT role, content_md FROM chat_messages WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, chat_answer.MAX_HISTORY),
        )
        history = [{"role": m["role"], "content": m["content_md"]} for m in reversed(history)]
        ai_text = chat_answer.answer(content, history, _material(chat, user), user["lang"], calls=calls)
    except ModelScopeAuthError:
        raise APIError("modelscope_token_invalid", 503) from None
    except AIError:
        raise APIError("ai_unavailable", 502) from None

    now = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
    db.write(
        f"INSERT INTO chat_messages (chat_id, role, content_md, created_at) VALUES (?, 'user', ?, {now})",
        (chat_id, content),
    )
    db.write(
        f"INSERT INTO chat_messages (chat_id, role, content_md, created_at) VALUES (?, 'ai', ?, {now})",
        (chat_id, ai_text),
    )
    if not chat["title"]:
        title = content[:60].replace("\n", " ").strip()
        db.write("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id))
    db.write(f"UPDATE chats SET updated_at = {now} WHERE id = ?", (chat_id,))
    # record the call (SPEC §7)
    for c in calls:
        db.write(
            "INSERT INTO ai_calls (user_id, feature, role, model, latency_ms, retries, ok)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user["id"], c["feature"], c["role"], c["model"], c["latency_ms"], c["retries"], 1 if c["ok"] else 0),
        )
    return _detail(chat_id, user)
