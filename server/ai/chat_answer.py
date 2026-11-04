"""Tanya (L7 task 4): one REASON call that answers a question, grounded on the
student's own summaries. `llm` is a module-level import so tests can
monkeypatch it with a FakeLLM instance.
"""
from __future__ import annotations

from server.ai import llm
from server.ai.prompts import chat_prompt

# The context is capped: summaries can be long, and the REASON call has a 120 s budget.
MAX_MATERIAL_CHARS = 24000
MAX_HISTORY = 6  # the last N messages travel with the call
MAX_QUESTION_CHARS = 2000

# The DB/API contract uses role "ai"; the chat API only accepts
# system/assistant/user. Map at this boundary (ModelScope rejects "ai" with a 400).
_LLM_ROLES = {"user": "user", "ai": "assistant"}


def build_messages(question: str, history: list[dict], material: str, lang: str) -> list[dict]:
    system = chat_prompt(lang)
    if material.strip():
        system += "\n\nThe student's summaries (context):\n\n" + material.strip()[:MAX_MATERIAL_CHARS]
    msgs: list[dict] = [{"role": "system", "content": system}]
    for m in history[-MAX_HISTORY:]:
        msgs.append({"role": _LLM_ROLES[m["role"]], "content": m["content"][:4000]})
    msgs.append({"role": "user", "content": question[:MAX_QUESTION_CHARS]})
    return msgs


def answer(question: str, history: list[dict], material: str, lang: str, calls: list[dict] | None = None) -> str:
    """One synchronous REASON call -> Markdown answer. Raises AIError /
    ModelScopeAuthError like every other llm.chat caller (mapped by the router)."""
    calls = calls if calls is not None else []
    text = llm.chat(
        "REASON",
        build_messages(question, history, material, lang),
        feature="chat_answer",
        calls=calls,
    )
    return str(text).strip()
