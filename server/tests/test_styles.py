"""L7b: the "flashcards" summary style maps to the "kartu" pipeline style."""
from __future__ import annotations

from server.ai import prompts
from server.tests.test_api_core import _register


def test_flashcards_style_is_queued_as_kartu(client, monkeypatch) -> None:
    seen: dict = {}
    monkeypatch.setattr("server.api.summaries.ms_state", lambda: {"status": "ok", "latency_ms": 1, "updated_at": 0.0})
    monkeypatch.setattr("server.jobs.runner.submit", lambda job_id, user_id, files, options: seen.update(options))

    user = _register(client, "kartutest")
    r = client.post(
        "/api/summaries",
        headers=user["headers"],
        files=[("files", ("catatan.txt", b"Sel adalah unit terkecil kehidupan.", "text/plain"))],
        data={"style": "flashcards", "lang": "id"},
    )
    assert r.status_code == 202, r.text
    assert seen["style"] == "kartu"

    bad = client.post(
        "/api/summaries",
        headers=user["headers"],
        files=[("files", ("catatan.txt", b"x", "text/plain"))],
        data={"style": "mindmap", "lang": "id"},
    )
    assert bad.status_code == 422


def test_kartu_reduce_prompt_keeps_language_line() -> None:
    p = prompts.reduce_prompt("kartu", "id")
    assert "flashcards" in p
    assert p.rstrip().endswith("Respond only in id.")
