"""Orvina AI package (SPEC §7).

Only this package may import `openai` (SPEC §2.1); only llm.py creates a
client. L1: the real LLM client (llm.py), extraction (extract.py) and the
summarize pipeline (summarize.py); FakeLLM for tests.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from server.ai.errors import AIError, ModelScopeAuthError  # re-exported (SPEC §7)
from server.ai.probe import modelscope_probe, ms_state, trigger_whisper_load, whisper_state
from server.ai.summarize import summarize  # real pipeline (L1)


def health() -> dict[str, Any]:
    """SPEC §7: {modelscope, whisper}. Uses the cached probe (no live call)."""
    return {"modelscope": ms_state()["status"], "whisper": whisper_state()["status"]}


def transcribe(job_id: str, path: str, options: dict, on_stage: Callable[[str], None]) -> dict[str, Any]:
    """SPEC §7 F2: media or transcript file; options {source_lang, targets[], summary}."""
    raise NotImplementedError("P2: ai/transcribe.py")


def forum_similar(title: str, body: str, candidates: list[dict]) -> dict[str, Any]:
    """SPEC §7: candidates = FTS5 top 10 [{id, title, excerpt}] -> {ids[<=3]}."""
    raise NotImplementedError("P2: ai/forum_ai.py")


def forum_tags(title: str, body: str) -> dict[str, Any]:
    """SPEC §7: -> {tags[<=5]} lowercase."""
    raise NotImplementedError("P2: ai/forum_ai.py")


def forum_moderate(text: str) -> dict[str, Any]:
    """SPEC §7: -> {allowed, reason_key}; fails open on API error."""
    raise NotImplementedError("P2: ai/forum_ai.py")


def forum_hint(question_md: str, answers_md: str, lang: str) -> dict[str, Any]:
    """SPEC §7: -> {hint_md}; a hint or guiding question, never the final answer."""
    raise NotImplementedError("P2: ai/forum_ai.py")


class FakeLLM:
    """Deterministic stand-in for the ModelScope client, for tests (L1+).

    Mirrors the real client shape: chat(role, messages, *, json_schema=None,
    images=None, feature, calls). Every call is recorded in self.calls, and a
    {feature, role, model, latency_ms, retries, ok} entry is appended to the
    caller's `calls` list, same as llm.chat. `reduce_sequence` scripts the
    reduce/repair outputs to exercise the format check.
    """

    def __init__(
        self,
        *,
        reduce_sequence: list[str] | None = None,
        reduce_output: str | None = None,
        repair_output: str | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self.reduce_sequence: list[str] = list(reduce_sequence or [])
        self.reduce_output = reduce_output
        self.repair_output = repair_output

    def chat(
        self,
        role: str,
        messages: list[dict],
        *,
        json_schema: dict | None = None,
        images: list[str] | None = None,
        feature: str = "test",
        calls: list[dict] | None = None,
        temperature: float | None = None,
    ) -> Any:
        self.calls.append(
            {
                "role": role,
                "feature": feature,
                "messages": messages,
                "json_schema": json_schema,
                "images": images,
                "temperature": temperature,
            }
        )
        if calls is not None:
            calls.append({"feature": feature, "role": role, "model": "fake/fake", "latency_ms": 1, "retries": 0, "ok": True})
        if feature == "map":
            return "Catatan: poin penting dari chunk ini. Rumus $a=b$."
        if feature == "reduce":
            if self.reduce_sequence:
                return self.reduce_sequence.pop(0)
            if self.reduce_output is not None:
                return self.reduce_output
            return "# Judul\n\n## TL;DR\n- poin 1\n- poin 2\n- poin 3\n"
        if feature == "format_repair":
            return self.repair_output if self.repair_output is not None else "# Judul\n\n## TL;DR\n- poin 1\n\nRumus $a=b$ dan $$c=d$$."
        if feature == "deadlines":
            if json_schema is not None:
                return [
                    {
                        "title": "Ujian",
                        "kind": "tenggat",
                        "subkind": "ujian",
                        "date": "2026-11-04",
                        "time": None,
                        "evidence": "ujian 4 November",
                    }
                ]
            return "[]"
        if feature == "schedule_import":
            if json_schema is not None:
                return [
                    {
                        "title": "Kuis Fisika",
                        "kind": "tenggat",
                        "subkind": "ujian",
                        "start_at": "2026-11-10T09:00",
                        "end_at": "2026-11-10T11:00",
                        "location": "Lab 2",
                    },
                    {
                        "title": "Kumpul Kelompok",
                        "kind": "belajar",
                        "subkind": None,
                        "start_at": "2026-11-12",
                        "end_at": None,
                        "location": None,
                    },
                ]
            return "[]"
        if feature == "chat_answer":
            return (
                "Jawaban tes untuk pertanyaan: "
                + (messages[-1]["content"][:80] if messages else "?")
                + "\n\n## Catatan\n- poin dari materi\n- rumus $a = b$"
            )
        if feature == "extract_image":
            return "Teks gambar: $E=mc^2$ dan `print(1)`."
        return "OK"


__all__ = [
    "AIError",
    "FakeLLM",
    "ModelScopeAuthError",
    "forum_hint",
    "forum_moderate",
    "forum_similar",
    "forum_tags",
    "health",
    "modelscope_probe",
    "ms_state",
    "summarize",
    "transcribe",
    "trigger_whisper_load",
    "whisper_state",
]
