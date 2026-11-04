"""LLM client (SPEC §9.1). The only place in the app that calls a model.

Role -> model (only the four allowed models, SPEC §2 / _LEAN §1; the FAST role
maps to Qwen because Step-3.5-Flash returns "no provider supported"):

    VISION  Qwen/Qwen3.8-27B
    FAST    Qwen/Qwen3.8-27B
    REASON  deepseek-ai/DeepSeek-V4-Pro-0813
    CHECK   zai-org/GLM-5.2

`openai` is imported only inside server/ai/ (SPEC §2.1) and only when a call
is actually made. Every call appends {feature, role, model, latency_ms,
retries, ok} to the caller's `calls` list (SPEC §7).
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import time
from typing import Any

import pydantic

from server.ai.errors import AIError, ModelScopeAuthError

log = logging.getLogger("orvina.ai")

MODELSCOPE_BASE = "https://api-inference.modelscope.ai/v1"
# The four allowed models (SPEC §2.1). Model IDs live ONLY here (and config.py).
ALLOWED_MODELS = frozenset(
    {
        "zai-org/GLM-5.2",
        "deepseek-ai/DeepSeek-V4-Pro-0813",
        "stepfun-ai/Step-3.5-Flash",
        "Qwen/Qwen3.8-27B",
    }
)
ROLE_MODELS: dict[str, str] = {
    "VISION": "Qwen/Qwen3.8-27B",
    # Step-3.5-Flash is down on the platform ("no provider supported");
    # _LEAN §1 moves the FAST role to Qwen.
    "FAST": "Qwen/Qwen3.8-27B",
    "REASON": "deepseek-ai/DeepSeek-V4-Pro-0813",
    "CHECK": "zai-org/GLM-5.2",
}
TIMEOUT_S = 120.0
MAX_RETRIES = 2
RETRY_BACKOFF_S = 1.0
MAX_IMAGE_PX = 1600


def _get_client() -> Any:
    """Lazily create the shared OpenAI client on MODELSCOPE_TOKEN. Tests monkeypatch this."""
    global _client
    if _client is None:
        from openai import OpenAI

        token = os.environ.get("MODELSCOPE_TOKEN") or ""
        _client = OpenAI(base_url=MODELSCOPE_BASE, api_key=token or "missing-token", timeout=TIMEOUT_S)
    return _client


_client: Any = None


def _is_retryable(exc: BaseException, status: int | None) -> bool:
    """429, 5xx and timeouts are retried; everything else is not (SPEC §9.1)."""
    if status is not None:
        return status == 429 or 500 <= status < 600
    from openai import APIConnectionError, APITimeoutError

    return isinstance(exc, (APIConnectionError, APITimeoutError))


def _record(calls: list[dict], *, feature: str, role: str, model: str, t0: float, retries: int, ok: bool, error: str | None = None) -> None:
    entry = {
        "feature": feature,
        "role": role,
        "model": model,
        "latency_ms": int((time.monotonic() - t0) * 1000),
        "retries": retries,
        "ok": ok,
    }
    if error:
        entry["error"] = error
    calls.append(entry)


def _create_once(model: str, messages: list[dict], *, temperature: float | None = None) -> tuple[str, int]:
    """One logical completion with the retry loop. Returns (text, retries).

    Raises ModelScopeAuthError on 401 (no retry) and AIError when the
    retries are exhausted.
    """
    client = _get_client()
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, **({"temperature": temperature} if temperature is not None else {})
            )
            return (resp.choices[0].message.content or "").strip(), attempt
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            if status == 401:
                raise ModelScopeAuthError("ModelScope returned 401 (invalid token)") from exc
            if _is_retryable(exc, status) and attempt < MAX_RETRIES:
                log.warning("llm %s attempt %d failed (%s); retrying", model, attempt + 1, str(exc)[:200])
                time.sleep(RETRY_BACKOFF_S * (attempt + 1))
                continue
            log.warning("llm %s call failed (%s): %s", model, status or "no-status", str(exc)[:300])
            raise AIError("llm_unreachable", {"detail": str(exc)[:200]}) from exc
    raise AssertionError("unreachable")


def _encode_images(images: list[str]) -> list[dict]:
    """Resize to at most 1600 px (longest side) and base64-encode (SPEC §9.1)."""
    from PIL import Image

    parts: list[dict] = []
    for path in images:
        img = Image.open(path)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        w, h = img.size
        scale = min(1.0, MAX_IMAGE_PX / max(w, h))
        if scale < 1.0:
            img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    return parts


_TYPE_MAP = {"string": str, "number": float, "integer": int, "boolean": bool, "array": list, "object": dict}


def _py_type(spec: dict) -> Any:
    t = spec.get("type", "string")
    if isinstance(t, list):  # e.g. ["string", "null"]
        nullable = "null" in t
        t = next((x for x in t if x != "null"), "string")
    else:
        nullable = False
    base = _TYPE_MAP.get(t, Any)
    return base | None if nullable else base


def _model_from_schema(schema: dict) -> Any:
    """Build a pydantic model from the JSON-Schema subset we use (SPEC §9.1)."""
    if schema.get("type") == "array":
        item = _model_from_schema(schema.get("items", {}))
        return list[item]  # type: ignore[valid-type]
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields: dict[str, Any] = {}
    for name, spec in props.items():
        fields[name] = (_py_type(spec), ... if name in required else None)
    return pydantic.create_model("OrvinaJson", **fields)


def _extract_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    starts = [i for i in (t.find("{"), t.find("[")) if i >= 0]
    ends = [i for i in (t.rfind("}"), t.rfind("]")) if i >= 0]
    if not starts or not ends:
        raise AIError("llm_bad_json", {"detail": "no JSON value in response"})
    start, end = min(starts), max(ends)
    if end <= start:
        raise AIError("llm_bad_json", {"detail": "malformed JSON in response"})
    return t[start : end + 1]


def _loads_tolerant(blob: str) -> Any:
    """json.loads with a trailing-comma fallback (BUG-01: models emit ",]")."""
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", blob))
    except json.JSONDecodeError as exc:
        raise AIError("llm_bad_json", {"detail": f"invalid JSON: {exc.msg}"}) from exc


def _validate_json(text: str, schema: dict) -> Any:
    from pydantic import TypeAdapter

    raw = _loads_tolerant(_extract_json(text))
    model = _model_from_schema(schema)
    try:
        data = TypeAdapter(model).validate_python(raw)
    except Exception as exc:
        raise AIError("llm_bad_json", {"detail": str(exc)[:300]}) from exc
    return data.model_dump() if hasattr(data, "model_dump") else raw


def chat(
    role: str,
    messages: list[dict],
    *,
    json_schema: dict | None = None,
    images: list[str] | None = None,
    feature: str,
    calls: list[dict],
    temperature: float | None = None,
) -> Any:
    """One model call (SPEC §9.1). Returns the text, or the validated dict for
    json_schema calls (one repair retry on bad JSON).

    Raises ValueError for a disallowed role/model/image use, ModelScopeAuthError
    on 401, AIError when the model cannot be reached or never returns valid JSON.
    """
    model = ROLE_MODELS.get(role)
    if model is None:
        raise ValueError(f"unknown role {role!r} (allowed: {', '.join(sorted(ROLE_MODELS))})")
    if model not in ALLOWED_MODELS:
        raise ValueError(f"model {model!r} is not one of the allowed models (SPEC §2)")
    if images and role != "VISION":
        raise ValueError("images are only allowed for the VISION role (SPEC §9.1)")

    msgs = [dict(m) for m in messages]
    if images:
        parts: list[dict] = [{"type": "text", "text": "Look at this image."}]
        parts.extend(_encode_images(images))
        if msgs and msgs[-1].get("role") == "user" and isinstance(msgs[-1].get("content"), str):
            if msgs[-1]["content"]:
                parts.insert(0, {"type": "text", "text": msgs[-1]["content"]})
            msgs[-1] = {"role": "user", "content": parts}
        else:
            msgs.append({"role": "user", "content": parts})
    if json_schema is not None:
        msgs.insert(
            0,
            {
                "role": "system",
                "content": "Answer with a single JSON value that validates against this JSON Schema. No prose, no code fences:\n"
                + json.dumps(json_schema, ensure_ascii=False),
            },
        )

    t0 = time.monotonic()
    try:
        text, retries = _create_once(model, msgs, temperature=temperature)
    except ModelScopeAuthError as exc:
        _record(calls, feature=feature, role=role, model=model, t0=t0, retries=0, ok=False, error="auth_401")
        raise exc
    except AIError as exc:
        detail = str(exc.params.get("detail", ""))[:200]
        _record(calls, feature=feature, role=role, model=model, t0=t0, retries=MAX_RETRIES, ok=False, error=detail)
        raise

    if json_schema is None:
        _record(calls, feature=feature, role=role, model=model, t0=t0, retries=retries, ok=True)
        return text

    try:
        data = _validate_json(text, json_schema)
        _record(calls, feature=feature, role=role, model=model, t0=t0, retries=retries, ok=True)
        return data
    except AIError as first_err:
        # One repair retry (SPEC §9.1): show the bad output and the error.
        log.warning("json parse failed for %s: %s; one repair retry", feature, first_err.params.get("detail", ""))
        repair_user = (
            "Your previous answer is not valid. Error: "
            f"{first_err.params.get('detail', 'bad JSON')}\nReturn only the corrected JSON value."
        )
        repair_msgs = [*msgs, {"role": "assistant", "content": text}, {"role": "user", "content": repair_user}]
        try:
            text2, retries2 = _create_once(model, repair_msgs, temperature=temperature)
        except (ModelScopeAuthError, AIError) as exc:
            _record(calls, feature=feature, role=role, model=model, t0=t0, retries=retries + 1, ok=False, error=str(exc)[:200])
            raise
        try:
            data = _validate_json(text2, json_schema)
        except AIError as second_err:
            detail = str(second_err.params.get("detail", ""))[:200]
            _record(calls, feature=feature, role=role, model=model, t0=t0, retries=retries + 1 + retries2, ok=False, error=detail)
            raise second_err from first_err
        _record(calls, feature=feature, role=role, model=model, t0=t0, retries=retries + 1 + retries2, ok=True)
        return data


__all__ = ["ALLOWED_MODELS", "MODELSCOPE_BASE", "ROLE_MODELS", "chat"]
