"""Me router (SPEC §6): GET /api/me and PATCH (display_name, lang, theme only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from server.api.auth import user_payload
from server.api.deps import get_current_user
from server.api.errors import APIError
from server.store import db

router = APIRouter(tags=["Me"])

LEAN_LANGS = ("id", "en")  # zh is a scope cut
THEMES = ("system", "light", "dark")


class PatchMeRequest(BaseModel):
    display_name: str | None = None
    lang: str | None = None
    theme: str | None = None


def _fetch(user_id: int) -> dict:
    row = db.read_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if row is None:
        raise APIError("unauthenticated", 401)
    return dict(row)


@router.get("/api/me")
def get_me(user: dict = Depends(get_current_user)) -> dict:
    row = _fetch(user["id"])
    # Cut features (points, leaderboard, notifications) report neutral zeros.
    return {
        "user": user_payload(row),
        "points": 0,
        "rank": 1,
        "unread": 0,
        "onboarding_done": bool(row["onboarding_done"]),
    }


@router.patch("/api/me")
def patch_me(body: PatchMeRequest, user: dict = Depends(get_current_user)) -> dict:
    sets: list[str] = []
    params: list[str] = []
    if body.display_name is not None:
        if not 1 <= len(body.display_name) <= 50:
            raise APIError("validation", 422)
        sets.append("display_name = ?")
        params.append(body.display_name)
    if body.lang is not None:
        if body.lang not in LEAN_LANGS:
            raise APIError("validation", 422)
        sets.append("lang = ?")
        params.append(body.lang)
    if body.theme is not None:
        if body.theme not in THEMES:
            raise APIError("validation", 422)
        sets.append("theme = ?")
        params.append(body.theme)
    if not sets:
        raise APIError("validation", 422)
    params.append(str(user["id"]))
    db.write(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", tuple(params))
    return user_payload(_fetch(user["id"]))
