"""L1 AI core tests.

Covers (per the L1 prompt): stage order via on_stage, format repair runs
exactly once, 401 raises ModelScopeAuthError, a disallowed role is rejected,
DOCX and TXT extraction. Fixture files are created at test time (no binaries
committed). No network: llm.chat is exercised through a fake client.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from server.ai import FakeLLM, summarize
from server.ai.errors import AIError, ModelScopeAuthError
from server.ai.extract import extract_file, extract_files
from server.ai.llm import chat as real_chat
from server.ai.summarize import chunk_text

BROKEN_MD = "Isi $a belum ditutup $$ dan ```python\ncode"


def _txt_file(tmp_path, name: str = "catatan.txt") -> str:
    p = tmp_path / name
    p.write_text("Limit fungsi adalah nilai yang didekati. " * 20 + "\nUjian akhir 4 November 2026.", encoding="utf-8")
    return str(p)


# --- llm.chat behaviour (fake client, no network) ----------------------------


def _patch_client(monkeypatch, client) -> None:
    monkeypatch.setattr("server.ai.llm.RETRY_BACKOFF_S", 0.0)
    monkeypatch.setattr("server.ai.llm._get_client", lambda: client)


def test_401_raises_modelscope_auth_error_without_retry(monkeypatch):
    class _AuthError(Exception):
        status_code = 401

    def create(**_kw):
        raise _AuthError("unauthorized")

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    calls: list[dict] = []
    _patch_client(monkeypatch, client)
    with pytest.raises(ModelScopeAuthError):
        real_chat("FAST", [{"role": "user", "content": "hi"}], feature="t", calls=calls)
    assert calls[0]["ok"] is False
    assert calls[0]["error"] == "auth_401"


def test_5xx_retries_then_succeeds(monkeypatch):
    class _ServerErr(Exception):
        status_code = 503

    attempts = {"n": 0}

    def create(**_kw):
        attempts["n"] += 1
        if attempts["n"] <= 2:
            raise _ServerErr("boom")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="halo"))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    calls: list[dict] = []
    _patch_client(monkeypatch, client)
    out = real_chat("REASON", [{"role": "user", "content": "hi"}], feature="t", calls=calls)
    assert out == "halo"
    assert attempts["n"] == 3
    assert calls[0]["retries"] == 2
    assert calls[0]["ok"] is True


def test_rejects_unknown_role():
    with pytest.raises(ValueError):
        real_chat("SUPER", [{"role": "user", "content": "hi"}], feature="t", calls=[])


def test_rejects_images_outside_vision():
    with pytest.raises(ValueError):
        real_chat("FAST", [{"role": "user", "content": "hi"}], images=["a.png"], feature="t", calls=[])


def test_json_one_repair_retry(monkeypatch):
    seq = iter(['{"title": "Ujian", "start_at": "2026-11-04", "evidence": "e"}', "garbage not json"])

    def create(**_kw):
        # first call valid, second (repair attempt) garbage -> final failure
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=next(seq)))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    calls: list[dict] = []
    _patch_client(monkeypatch, client)
    schema = {
        "type": "object",
        "properties": {"title": {"type": "string"}, "start_at": {"type": "string"}, "evidence": {"type": "string"}},
        "required": ["title", "start_at", "evidence"],
    }
    out = real_chat("CHECK", [{"role": "user", "content": "x"}], json_schema=schema, feature="deadlines", calls=calls)
    assert out["title"] == "Ujian"
    assert calls[0]["retries"] == 0
    assert calls[0]["ok"] is True


def test_json_fails_after_one_repair(monkeypatch):
    def create(**_kw):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="garbage not json"))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    calls: list[dict] = []
    _patch_client(monkeypatch, client)
    schema = {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}
    with pytest.raises(AIError):
        real_chat("CHECK", [{"role": "user", "content": "x"}], json_schema=schema, feature="deadlines", calls=calls)
    assert calls[0]["ok"] is False
    assert calls[0]["retries"] == 1


# --- summarize pipeline (FakeLLM) --------------------------------------------


def test_stage_order_and_result(tmp_path):
    llm = FakeLLM()
    stages: list[str] = []
    result = summarize(
        "job-1",
        [{"path": _txt_file(tmp_path), "name": "catatan.txt", "mime": "text/plain"}],
        {"style": "ringkas", "lang": "id"},
        stages.append,
        llm=llm,
    )
    assert stages == ["extract", "chunk", "map", "reduce", "check", "deadlines"]
    assert result["figures"] == []
    assert result["sources"][0]["label"] == "catatan.txt"
    assert result["deadlines"][0]["title"] == "Ujian"
    assert result["deadlines"][0]["start_at"] == "2026-11-04"
    assert result["warning"] is False
    assert len(result["ai_calls"]) == len(llm.calls)
    assert len(llm.calls) >= 3  # map + reduce + deadlines


def test_format_repair_runs_once(tmp_path):
    llm = FakeLLM(reduce_sequence=[BROKEN_MD])
    result = summarize(
        "job-2",
        [{"path": _txt_file(tmp_path), "name": "catatan.txt", "mime": "text/plain"}],
        {},
        lambda _s: None,
        llm=llm,
    )
    repairs = [c for c in llm.calls if c["feature"] == "format_repair"]
    assert len(repairs) == 1
    assert result["warning"] is False
    assert result["content_md"] != BROKEN_MD


def test_format_repair_failure_sets_warning(tmp_path):
    llm = FakeLLM(reduce_output=BROKEN_MD, repair_output=BROKEN_MD)
    result = summarize(
        "job-3",
        [{"path": _txt_file(tmp_path), "name": "catatan.txt", "mime": "text/plain"}],
        {},
        lambda _s: None,
        llm=llm,
    )
    repairs = [c for c in llm.calls if c["feature"] == "format_repair"]
    assert len(repairs) == 1
    assert result["warning"] is True
    assert "format_check_failed" in result["warnings"]


def test_empty_input_raises(tmp_path):
    p = tmp_path / "kosong.txt"
    p.write_text("", encoding="utf-8")
    with pytest.raises(AIError) as ei:
        summarize("job-4", [{"path": str(p), "name": "kosong.txt", "mime": "text/plain"}], {}, lambda _s: None, llm=FakeLLM())
    assert ei.value.code == "nothing_to_summarize"


# --- extraction ---------------------------------------------------------------


def test_docx_and_txt_extraction(tmp_path):
    from docx import Document

    docx_path = tmp_path / "modul.docx"
    doc = Document()
    doc.add_paragraph("Rumus luas lingkaran: A = r^2.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Nama"
    table.cell(0, 1).text = "Nilai"
    table.cell(1, 0).text = "A"
    table.cell(1, 1).text = "90"
    doc.save(str(docx_path))
    txt_path = tmp_path / "catatan.txt"
    txt_path.write_text("Pertemuan 3 membahas limit fungsi.", encoding="utf-8")

    docx_mime = "docx"  # dispatch is by name extension here; the real MIME is long
    text, warnings, sources = extract_files(
        [
            {"path": str(docx_path), "name": "modul.docx", "mime": docx_mime},
            {"path": str(txt_path), "name": "catatan.txt", "mime": "text/plain"},
        ],
        llm=FakeLLM(),
        calls=[],
    )
    assert "luas lingkaran" in text
    assert "Nama | Nilai" in text
    assert "limit fungsi" in text
    assert [s["label"] for s in sources] == ["modul.docx", "catatan.txt"]
    assert warnings == []


def test_unsupported_format_rejected(tmp_path):
    p = tmp_path / "x.exe"
    p.write_bytes(b"MZ")
    with pytest.raises(AIError) as ei:
        extract_file(str(p), "x.exe", "application/x-msdownload", llm=FakeLLM(), calls=[])
    assert ei.value.code == "unsupported_format"


def test_image_extraction_via_vision(tmp_path):
    p = tmp_path / "rumus.png"
    p.write_bytes(b"\x89PNG-fake")  # FakeLLM never opens the file
    text, warnings, sources = extract_files([{"path": str(p), "name": "rumus.png", "mime": "image/png"}], llm=FakeLLM(), calls=[])
    assert "E=mc^2" in text
    assert sources[0]["label"] == "rumus.png"
    assert warnings == []


def test_chunk_on_label_boundaries():
    text = "\n\n".join(f"## Hal. {i}\n\n" + ("isi " * 400) for i in range(1, 5))
    chunks = chunk_text(text)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= 6000 * 2
        assert c.startswith("## Hal.")
