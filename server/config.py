"""Environment configuration (SPEC §4.1).

Secrets come from environment variables only (SPEC §2.5): Studio Secrets in
production, .env locally. Nothing here is logged.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PORT_DEFAULT = 7860
MAX_UPLOAD_MB_DEFAULT = 200
MAX_MEDIA_MINUTES_DEFAULT = 15
JOB_WORKERS_DEFAULT = 2
WHISPER_MODEL_DEFAULT = "base"


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    return v.strip().lower() not in ("0", "false", "no", "off")


def _int(name: str, default: int) -> int:
    v = os.environ.get(name)
    try:
        return int(v) if v not in (None, "") else default
    except ValueError:
        return default


def data_dir() -> Path:
    """DATA_DIR: /data if writable, else /tmp/orvina (SPEC §4.1)."""
    env = os.environ.get("DATA_DIR")
    p = Path(env) if env else (Path("/data") if os.access("/data", os.W_OK) else Path("/tmp/orvina"))
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass(frozen=True)
class Settings:
    port: int
    public_app_url: str
    data_dir: Path
    enable_transcription: bool
    whisper_model: str
    whisper_preload: bool
    max_media_minutes: int
    max_upload_mb: int
    job_workers: int
    has_google: bool
    missing_required: tuple[str, ...]


def load_settings() -> Settings:
    missing = [n for n in ("MODELSCOPE_TOKEN", "APP_SECRET_KEY") if not os.environ.get(n)]
    return Settings(
        port=_int("PORT", PORT_DEFAULT),
        public_app_url=os.environ.get("PUBLIC_APP_URL", ""),
        data_dir=data_dir(),
        # Scope cut: F2 / audio-video input dropped, so transcription is OFF by
        # default. Every feature must still work with it off (SPEC §2.3).
        enable_transcription=_bool("ENABLE_TRANSCRIPTION", False),
        whisper_model=os.environ.get("WHISPER_MODEL", WHISPER_MODEL_DEFAULT),
        whisper_preload=_bool("WHISPER_PRELOAD", False),
        max_media_minutes=_int("MAX_MEDIA_MINUTES", MAX_MEDIA_MINUTES_DEFAULT),
        max_upload_mb=_int("MAX_UPLOAD_MB", MAX_UPLOAD_MB_DEFAULT),
        job_workers=_int("JOB_WORKERS", JOB_WORKERS_DEFAULT),
        has_google=bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET")),
        missing_required=tuple(missing),
    )


settings = load_settings()
