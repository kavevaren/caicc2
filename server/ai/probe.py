"""P0 platform probe: ModelScope health + whisper loader.

Moved from the v4 engine (arsip/engine-v4/main.py) into `server/ai/` so that
`openai` is imported nowhere outside `server/ai/` (SPEC §2.1). The model IDs
live only in llm.py (L1); the probe reuses them here.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any

from server.ai.llm import ALLOWED_MODELS, MODELSCOPE_BASE, ROLE_MODELS

# --- shared data directory (SPEC §4.1: /data if writable, else /tmp/orvina) --


def data_dir() -> Path:
    from server.config import data_dir as _config_data_dir

    return _config_data_dir()


# --- ModelScope probe --------------------------------------------------------

_ms_state: dict[str, Any] = {"status": "checking", "latency_ms": 0, "updated_at": 0.0}


def ms_state() -> dict[str, Any]:
    """The cached probe result (refreshed by ms_loop every 5 min, SPEC §6)."""
    return dict(_ms_state)


def _probe_model() -> str:
    """Model for the health probe: FAST by default (P0 prompt), overridable with
    PROBE_MODEL because the platform can drop a model at any time (observed:
    Step-3.5-Flash returned 'no provider supported' on 2026-10-31). Only the
    four allowed models are accepted (SPEC §2.1)."""
    m = os.environ.get("PROBE_MODEL", ROLE_MODELS["FAST"])
    if m not in ALLOWED_MODELS:
        raise ValueError(f"PROBE_MODEL {m!r} is not an allowed model")
    return m


def modelscope_probe() -> tuple[str, int]:
    """One tiny FAST chat completion. Returns (status, latency_ms)."""
    token = os.environ.get("MODELSCOPE_TOKEN") or ""
    if not token:
        return "invalid_token", 0
    try:
        from openai import OpenAI

        client = OpenAI(base_url=MODELSCOPE_BASE, api_key=token, timeout=30.0)
        t0 = time.monotonic()
        client.chat.completions.create(
            model=_probe_model(),
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )
        return "ok", int((time.monotonic() - t0) * 1000)
    except Exception as exc:
        msg = str(exc).lower()
        if "401" in msg or "unauthorized" in msg:
            return "invalid_token", 0
        import logging

        logging.getLogger("orvina.ai").warning("modelscope probe failed: %s", str(exc)[:300])
        return "unreachable", 0


def ms_loop(period_s: float = 300.0) -> None:
    """Background thread: refresh the cached probe result every 5 min (SPEC §6)."""
    while True:
        status, latency = modelscope_probe()
        _ms_state.update(status=status, latency_ms=latency, updated_at=time.time())
        time.sleep(period_s)


# --- whisper (lazy, one global lock, CPU int8 — SPEC §9.2) -------------------

# Scope cut: ENABLE_TRANSCRIPTION defaults to false (matches server/config.py),
# so /api/health reports whisper as "disabled", not an error or a load in progress.
_whisper_state: dict[str, Any] = {
    "status": "disabled" if os.environ.get("ENABLE_TRANSCRIPTION", "false").lower() != "true" else "idle",
    "model": None,
    "lock": threading.Lock(),
    "loading_started": False,
}


def _load_whisper() -> None:
    import logging

    name = os.environ.get("WHISPER_MODEL", "base")
    local_dir = str(data_dir() / "models")
    with _whisper_state["lock"]:
        if _whisper_state["model"] is not None:
            return
        try:
            from faster_whisper import WhisperModel

            model = WhisperModel(name, device="cpu", compute_type="int8", download_root=local_dir)
            _whisper_state["model"] = model
            _whisper_state["status"] = "ready"
        except Exception as exc:
            logging.getLogger("orvina.ai").exception("whisper load failed")
            _whisper_state["status"] = "error"
            _whisper_state["error"] = str(exc)[:200]


def trigger_whisper_load() -> str:
    """Start the one-shot background load (P0 probe endpoint). Idempotent."""
    if _whisper_state["status"] == "disabled":
        return "disabled"
    with _whisper_state["lock"]:
        if _whisper_state["model"] is None and not _whisper_state["loading_started"]:
            _whisper_state["loading_started"] = True
            _whisper_state["status"] = "loading"
            threading.Thread(target=_load_whisper, daemon=True).start()
    return _whisper_state["status"]


def whisper_state() -> dict[str, Any]:
    with _whisper_state["lock"]:
        return {
            "status": _whisper_state["status"],
            "model": os.environ.get("WHISPER_MODEL", "base"),
            "error": _whisper_state.get("error"),
        }
