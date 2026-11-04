"""Orvina — single FastAPI process (SPEC §4, §3.2).

One process on 0.0.0.0:${PORT:-7860} (one uvicorn worker):
- lifespan: migrate the DB -> seed if empty -> start the ModelScope probe loop;
  the port opens within seconds (whisper loads lazily, SPEC §13);
- serves web/dist with SPA fallback and /api/* (contracts/openapi.yaml);
- global error handlers: no stack trace ever reaches the browser.
"""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from server import __version__
from server.ai.probe import data_dir, ms_loop
from server.api import (
    auth,
    chat,
    dashboard,
    deps,  # noqa: F401  (rate limits, wired in P3)
    documents,
    errors,
    files,
    forum,
    health,
    jobs,
    me,
    notifications,
    points,
    projects,
    schedule,
    subjects,
    summaries,
    transcripts,
)
from server.config import settings
from server.jobs import runner
from server.seed import seed_if_empty
from server.store import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("orvina")

DIST_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Orvina %s starting (DATA_DIR=%s)", __version__, data_dir())
    if settings.missing_required:
        log.warning("required env vars missing: %s — auth/AI will fail until set (Studio Secrets)", ", ".join(settings.missing_required))
    db.run_migrations()
    seed_if_empty()
    runner.start()  # thread pool + fail jobs left running by an earlier process
    threading.Thread(target=ms_loop, daemon=True).start()
    if settings.whisper_preload and settings.enable_transcription:
        from server.ai import trigger_whisper_load

        trigger_whisper_load()
    yield
    log.info("Orvina stopped")


app = FastAPI(title="Orvina", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None)
errors.register_error_handlers(app)
for r in (
    health.router,
    auth.router,
    chat.router,
    me.router,
    subjects.router,
    dashboard.router,
    jobs.router,
    documents.router,
    transcripts.router,
    schedule.router,
    forum.router,
    points.router,
    projects.router,
    notifications.router,
    files.router,
    summaries.router,
):
    app.include_router(r)


# BUG-21: never let a browser/proxy cache API responses (stale calendar).
@app.middleware("http")
async def _no_store_api(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# --- static SPA (SPEC §13: relative URLs, SPA fallback) --------------------------


def _safe_file(path: str) -> Path | None:
    if not path:
        return DIST_DIR / "index.html"
    candidate = (DIST_DIR / path).resolve()
    if not candidate.is_relative_to(DIST_DIR.resolve()) or not candidate.is_file():
        return None
    return candidate


@app.get("/{full_path:path}")
async def spa(full_path: str) -> Any:
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404)
    candidate = _safe_file(full_path)
    if candidate is not None:
        return FileResponse(candidate)
    index = DIST_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    log.warning("web/dist not built; serving placeholder for /%s", full_path)
    return JSONResponse({"error": {"code": "frontend_not_built"}}, status_code=503)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server.main:app", host="0.0.0.0", port=settings.port, workers=1)
