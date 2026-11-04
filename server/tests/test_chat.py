"""L7 task 4 tests: Tanya (AI chat) — owner-only CRUD, the answer flow with a
FakeLLM (grounded on the chat's project), and the AI error gates.
"""
from __future__ import annotations

import re
from pathlib import Path

from server.store import db

ROOT = Path(__file__).resolve().parents[2]


def _register(client, username: str) -> dict:
    r = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "display_name": username.title(),
            "password": "password123",
            "lang": "id",
            "accept_terms": True,
        },
    )
    assert r.status_code == 201, r.text
    token = r.json()["token"]
    return {"token": token, "headers": {"Authorization": f"Bearer {token}"}}


def _user_id(username: str) -> int:
    return db.read_one("SELECT id FROM users WHERE username = ?", (username,))["id"]


def _make_doc(username: str, title: str, content: str) -> int:
    uid = _user_id(username)
    cur = db.write(
        "INSERT INTO documents (user_id, kind, title, content_md) VALUES (?, 'summary', ?, ?)",
        (uid, title, content),
    )
    return cur.lastrowid


def _pin_ai(client, monkeypatch, llm) -> None:
    import server.ai.chat_answer as ca
    from server.ai import chat_answer  # noqa: F401  (same module object)

    monkeypatch.setattr("server.api.chat.ms_state", lambda: {"status": "ok", "latency_ms": 1, "updated_at": 0.0})
    monkeypatch.setattr(ca, "llm", llm)


def test_chats_owner_only_crud(client) -> None:
    u = _register(client, "chat1")
    u2 = _register(client, "chat2")
    # create (no project) -> 201, empty title, no messages
    r = client.post("/api/chats", json={}, headers=u["headers"])
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["title"] == "" and c["messages"] == [] and c["project_id"] is None
    # create with a project the user owns
    pid = client.post("/api/projects", json={"title": "Proyek Chat"}, headers=u["headers"]).json()["id"]
    r = client.post("/api/chats", json={"project_id": pid}, headers=u["headers"])
    assert r.status_code == 201 and r.json()["project_id"] == pid and r.json()["project_title"] == "Proyek Chat"
    # a foreign / nonexistent project -> 404
    assert client.post("/api/chats", json={"project_id": 999999}, headers=u["headers"]).status_code == 404
    other = client.post("/api/projects", json={"title": "Milik orang lain"}, headers=u2["headers"]).json()["id"]
    assert client.post("/api/chats", json={"project_id": other}, headers=u["headers"]).status_code == 404
    # list: owner sees 2, the other user sees none
    items = client.get("/api/chats", headers=u["headers"]).json()["items"]
    assert len(items) == 2
    assert client.get("/api/chats", headers=u2["headers"]).json()["items"] == []
    # foreign chat -> 404 on get / delete
    assert client.get(f"/api/chats/{c['id']}", headers=u2["headers"]).status_code == 404
    assert client.delete(f"/api/chats/{c['id']}", headers=u2["headers"]).status_code == 404
    # owner delete -> 204 then 404 (messages cascade)
    assert client.delete(f"/api/chats/{c['id']}", headers=u["headers"]).status_code == 204
    assert client.get(f"/api/chats/{c['id']}", headers=u["headers"]).status_code == 404
    assert db.read_one("SELECT id FROM chat_messages WHERE chat_id = ?", (c["id"],)) is None


def test_chat_answer_with_fakellm(client, monkeypatch) -> None:
    from server.ai import FakeLLM

    fake = FakeLLM()
    _pin_ai(client, monkeypatch, fake)

    u = _register(client, "chat3")
    doc = _make_doc("chat3", "Turunan", "# Turunan\n\nAturan rantai: (f g)' = f' g'.")
    pid = client.post("/api/projects", json={"title": "UTS"}, headers=u["headers"]).json()["id"]
    client.post(f"/api/projects/{pid}/documents", json={"document_id": doc}, headers=u["headers"])
    c = client.post("/api/chats", json={"project_id": pid}, headers=u["headers"]).json()

    # first question: user + ai messages stored, title auto-set from the question
    r = client.post(
        f"/api/chats/{c['id']}/messages",
        json={"content": "Jelaskan aturan rantai dengan contoh."},
        headers=u["headers"],
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert [m["role"] for m in d["messages"]] == ["user", "ai"]
    assert d["messages"][0]["content_md"] == "Jelaskan aturan rantai dengan contoh."
    assert "Jawaban tes" in d["messages"][1]["content_md"]
    assert d["title"] == "Jelaskan aturan rantai dengan contoh."
    # the REASON call carried the project's summary as context
    call = next(x for x in fake.calls if x["feature"] == "chat_answer")
    assert call["role"] == "REASON"
    system = call["messages"][0]["content"]
    assert "Turunan" in system
    assert "(f g)'" in system
    # the ai_call row was recorded
    assert db.read_one("SELECT id FROM ai_calls WHERE feature = 'chat_answer'") is not None
    # second question: history is sent (user + ai of the first exchange);
    # the LLM boundary maps the contract role "ai" to "assistant"
    r = client.post(f"/api/chats/{c['id']}/messages", json={"content": "Kasih soal latihan."}, headers=u["headers"])
    assert r.status_code == 200
    call = fake.calls[-1]
    roles = [m["role"] for m in call["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    # blank content -> 422; a foreign chat's message endpoint -> 404
    assert client.post(f"/api/chats/{c['id']}/messages", json={"content": "   "}, headers=u["headers"]).status_code == 422
    u2 = _register(client, "chat4")
    assert client.post(f"/api/chats/{c['id']}/messages", json={"content": "Halo"}, headers=u2["headers"]).status_code == 404
    # list order: the active chat is first
    items = client.get("/api/chats", headers=u["headers"]).json()["items"]
    assert items[0]["id"] == c["id"] and items[0]["title"].startswith("Jelaskan aturan rantai")


def test_chat_answer_error_gates(client, monkeypatch) -> None:
    from server.ai import FakeLLM
    from server.ai.errors import AIError

    _pin_ai(client, monkeypatch, FakeLLM())
    u = _register(client, "chat5")
    c = client.post("/api/chats", json={}, headers=u["headers"]).json()
    # invalid token gate -> 503
    monkeypatch.setattr("server.api.chat.ms_state", lambda: {"status": "invalid_token", "latency_ms": 0, "updated_at": 0.0})
    r = client.post(f"/api/chats/{c['id']}/messages", json={"content": "Halo"}, headers=u["headers"])
    assert r.status_code == 503 and r.json()["error"]["code"] == "modelscope_token_invalid"
    # unreachable gate -> 502
    monkeypatch.setattr("server.api.chat.ms_state", lambda: {"status": "unreachable", "latency_ms": 0, "updated_at": 0.0})
    r = client.post(f"/api/chats/{c['id']}/messages", json={"content": "Halo"}, headers=u["headers"])
    assert r.status_code == 502 and r.json()["error"]["code"] == "ai_unavailable"
    # a runtime AIError while answering -> 502 ai_unavailable, nothing stored
    import server.ai.chat_answer as ca

    def boom(*args, **kwargs):
        raise AIError("model down")

    monkeypatch.setattr("server.api.chat.ms_state", lambda: {"status": "ok", "latency_ms": 1, "updated_at": 0.0})
    monkeypatch.setattr(ca, "answer", boom)
    r = client.post(f"/api/chats/{c['id']}/messages", json={"content": "Halo"}, headers=u["headers"])
    assert r.status_code == 502 and r.json()["error"]["code"] == "ai_unavailable"
    assert client.get(f"/api/chats/{c['id']}", headers=u["headers"]).json()["messages"] == []


def test_chat_inserts_use_explicit_column_lists() -> None:
    src = (ROOT / "server" / "api" / "chat.py").read_text(encoding="utf-8")
    n_inserts = len(re.findall(r"INSERT\s+INTO", src, re.I))
    n_with_cols = len(re.findall(r"INSERT\s+INTO\s+[A-Za-z_]+\s*\(", src, re.I))
    assert n_inserts >= 2
    assert n_inserts == n_with_cols, "every INSERT must name its columns"
