"""L7a progress tests (at most 2, per the L7a prompt).

(a) the map loop reports on_progress (0,n)...(n,n);
(b) the server percent uses fixed stage weights (map 2/4 -> 47 +- 1; done -> 100).
"""
from __future__ import annotations

from server.ai import FakeLLM
from server.ai.summarize import summarize
from server.jobs.runner import _percent


def test_map_reports_chunk_progress(tmp_path) -> None:
    # ~25k chars in one line -> 3 chunks (two 12k hard-splits + the remainder)
    path = tmp_path / "catatan.txt"
    path.write_text("Bab. " * 5000, encoding="utf-8")

    seen: list[tuple[int, int]] = []
    result = summarize(
        "job-progress",
        [{"path": str(path), "name": "catatan.txt", "mime": "text/plain"}],
        {"style": "ringkas", "lang": "id"},
        lambda stage: None,
        llm=FakeLLM(),
        on_progress=lambda done, total: seen.append((done, total)),
    )
    assert seen == [(0, 3), (1, 3), (2, 3), (3, 3)]
    assert result["content_md"].strip()


def test_percent_stage_weights() -> None:
    # map: 15 + 65 * (2/4) = 47.5 -> within 47 +- 1
    assert abs(_percent("map", (2, 4)) - 47) <= 1
    # done is always 100
    assert _percent("done", None) == 100
    # fixed lower bounds for the other stages
    assert _percent("queued", None) == 0
    assert _percent("extract", None) == 10
    assert _percent("deadlines", None) == 97
