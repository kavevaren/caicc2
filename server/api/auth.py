"""Auth router (SPEC §6): register / login / logout with Bearer session tokens.

Session token = 32 random bytes; only its sha256 is stored, 30-day expiry
(SPEC §5). Login failures are always the generic invalid_credentials.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel

from server.api.deps import extract_token, get_current_user
from server.api.errors import APIError
from server.store import db

router = APIRouter(tags=["Auth"])

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
SESSION_DAYS = 30
LEAN_LANGS = ("id", "en")  # zh is a scope cut


class RegisterRequest(BaseModel):
    username: str
    display_name: str
    password: str
    lang: str = "id"
    accept_terms: bool = False


class LoginRequest(BaseModel):
    username: str
    password: str


class StreamTicketRequest(BaseModel):
    job_id: str


def new_session(user_id: int) -> str:
    """Create a 30-day session; returns the raw token (hash is stored).

    Timestamp format matches the SQLite defaults elsewhere (millisecond
    'Z' form): Python's %f is microseconds, so the seconds are formatted
    explicitly to keep the string a valid, comparable timestamp.
    """
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    exp = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    expires = f"{exp:%Y-%m-%dT%H:%M:%S}.{exp.microsecond // 1000:03d}Z"
    db.write("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)", (token_hash, user_id, expires))
    return token


def user_payload(row: dict) -> dict:
    return {
        "username": row["username"],
        "display_name": row["display_name"],
        "lang": row["lang"],
        "theme": row["theme"],
        "reduce_motion": bool(row["reduce_motion"]),
        "onboarding_done": bool(row["onboarding_done"]),
    }


@router.post("/api/auth/register", status_code=201)
def register(body: RegisterRequest) -> dict:
    if not USERNAME_RE.match(body.username):
        raise APIError("invalid_username", 400)
    if len(body.password) < 8:
        raise APIError("weak_password", 400)
    if not body.accept_terms:
        raise APIError("terms_required", 400)
    if body.lang not in LEAN_LANGS:
        raise APIError("validation", 422)
    if db.read_one("SELECT id FROM users WHERE username = ?", (body.username,)) is not None:
        raise APIError("username_taken", 409)
    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt(12)).decode()
    cur = db.write(
        "INSERT INTO users (username, display_name, password_hash, lang, theme, onboarding_done) VALUES (?, ?, ?, ?, 'system', 1)",
        (body.username, body.display_name, pw_hash, body.lang),
    )
    token = new_session(int(cur.lastrowid))
    row = db.read_one("SELECT * FROM users WHERE id = ?", (int(cur.lastrowid),))
    return {"token": token, "user": user_payload(dict(row))}


@router.post("/api/auth/login")
def login(body: LoginRequest) -> dict:
    row = db.read_one("SELECT * FROM users WHERE username = ?", (body.username,))
    if row is None or not bcrypt.checkpw(body.password.encode(), row["password_hash"].encode()):
        raise APIError("invalid_credentials", 401)
    token = new_session(int(row["id"]))
    return {"token": token, "user": user_payload(dict(row))}


@router.post("/api/auth/logout", status_code=204)
def logout(
    user: dict = Depends(get_current_user),
    x_orvina_token: str = Header(default=""),
    authorization: str = Header(default=""),
) -> Response:
    token = extract_token(x_orvina_token, authorization)
    if token:
        db.write("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))
    return Response(status_code=204)


@router.post("/api/stream-ticket")
def create_stream_ticket(body: StreamTicketRequest, user: dict = Depends(get_current_user)) -> object:
    # SSE is a scope cut: polling GET /api/jobs/{id} is the only progress channel.
    from server.api.errors import not_implemented

    return not_implemented()
