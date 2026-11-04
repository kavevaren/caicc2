"""F1 summaries router (SPEC §6): POST /api/summaries starts a summary job.

Multipart: up to 10 files, each <= MAX_UPLOAD_MB, allowed extensions only.
Files are stored as uploads/<uuid>.<ext> (never the original name) and the
job is queued before the response — well under 2 s.
"""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile

from server.ai.probe import ms_state
from server.api.deps import get_current_user, require_upload_rate
from server.api.errors import APIError
from server.config import settings
from server.jobs import runner
from server.store import db

router = APIRouter(tags=["Summaries (F1)"])

ALLOWED_EXTS = {".pdf", ".pptx", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg"}
LEAN_LANGS = ("id", "en")
STYLES = ("one_page", "structured_notes", "key_points", "qa_practice", "flashcards")
MAX_FILES = 10


@router.post("/api/summaries", status_code=202)
def create_summary(
    user: dict = Depends(get_current_user),
    files: list[UploadFile] = File(default=[]),
    title: str | None = Form(default=None),
    subject_id: int | None = Form(default=None),
    style: str = Form(default="structured_notes"),
    lang: str = Form(default="id"),
    detail: str = Form(default="standar"),  # accepted for contract compat, lean ignores it
    extra: str | None = Form(default=None),
    notes: str | None = Form(default=None),  # FEAT-01: "Catatan untuk AI" (max 500)
    include_deadlines: bool = Form(default=True),  # "Masukkan tenggat ke Jadwal"
) -> dict:
    # AI gate (SPEC §6): 503 on invalid token, 502 when the platform is unreachable.
    ms = ms_state()["status"]
    if ms == "invalid_token":
        raise APIError("modelscope_token_invalid", 503)
    if ms == "unreachable":
        raise APIError("ai_unavailable", 502)
    if not files:
        raise APIError("validation", 422)
    if len(files) > MAX_FILES:
        raise APIError("validation", 422)
    if style not in STYLES:
        raise APIError("validation", 422)
    if lang not in LEAN_LANGS:
        raise APIError("validation", 422)
    if notes is not None and len(notes) > 500:
        raise APIError("validation", 422)
    require_upload_rate(user)

    max_bytes = settings.max_upload_mb * 1024 * 1024
    uploads_dir = settings.data_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    saved: list[dict] = []
    source_files: list[dict] = []
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in ALLOWED_EXTS:
            raise APIError("validation", 422)
        data = f.file.read()
        if len(data) > max_bytes:
            raise APIError("file_too_large", 413)
        stored_name = f"{uuid.uuid4()}{ext}"
        stored_path = uploads_dir / stored_name
        stored_path.write_bytes(data)
        saved.append({"path": str(stored_path), "name": f.filename or stored_name, "ext": ext, "size": len(data)})
        source_files.append({"name": f.filename or stored_name, "size_bytes": len(data)})

    job_id = str(uuid.uuid4())
    first_name = (files[0].filename or "ringkasan") if files else "ringkasan"
    db.write(
        "INSERT INTO jobs (id, user_id, kind, status, stage, stages_json, label, notes, created_at, updated_at)"
        " VALUES (?, ?, 'summary', 'queued', 'queued', '[]', ?, ?,"
        " strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
        (job_id, user["id"], first_name, (notes or "").strip()[:500] or None),
    )
    runner.submit(
        job_id,
        user["id"],
        saved,
        {
            "style": runner.STYLE_MAP[style],
            "lang": lang,
            "title": title,
            "subject_id": subject_id,
            "extra": extra,
            "notes": (notes or "").strip()[:500] or None,
            "include_deadlines": bool(include_deadlines),
            "source_files": source_files,
        },
    )
    return {"job_id": job_id}
