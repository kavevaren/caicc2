# L2 · API core: auth, jobs, documents, dashboard (budget ≈ 300)

**Read:**
- `prompts/lean/_LEAN.md`;
- `server/main.py`, `server/api/deps.py`, `server/api/errors.py` and `server/store/db.py`;
- in `docs/SPEC.md`, only §5 (lines ~141–173), §6 (lines ~175–201) and §8.1–§8.3 (lines ~225–248).
- In `contracts/openapi.yaml`, read only the blocks for `/api/auth/*`, `/api/me`, `/api/subjects`, `/api/dashboard`, `/api/jobs/{id}`, `/api/summaries`, `/api/documents*` and `/api/health` (search for each path and read that block).

**Work only in:** `server/api/`, `server/store/`, `server/jobs/`, `server/main.py`, `server/seed.py` and `server/tests/`. Call AI only through `server.ai.summarize`.

## Tasks
1. **Auth** (`auth.py`, `me.py`):
   - **register:** username `[A-Za-z0-9_]{3,20}`, password of at least 8 characters, `accept_terms` must be true (otherwise `terms_required`), bcrypt with cost 12, and set `onboarding_done=1`;
   - **login:** a generic `invalid_credentials` error;
   - **logout**;
   - **`GET /api/me`**;
   - **`PATCH /api/me`:** `display_name`, `lang` and `theme` only.
   - Session token: 32 random bytes; store its sha256 with a 30-day expiry.
   - Subjects: `GET` and `POST /api/subjects`.
2. **Jobs** (`server/jobs/runner.py`):
   - `POST /api/summaries` (multipart, at most 10 files, `MAX_UPLOAD_MB` each, allowed extensions only) saves the files as `uploads/<uuid>.<ext>`, creates the job and returns `{job_id}` in under 2 s.
   - A `ThreadPoolExecutor(JOB_WORKERS)` runs `ai.summarize`. `on_stage` updates `jobs.stage`.
   - **On success:** insert the `documents` row (`kind='summary'`), the `event_suggestions` from the deadlines, and the `ai_calls` rows. Write every INSERT with an explicit column list, and route every write through `store.db.write()`.
   - **On `AIError` or `ModelScopeAuthError`:** set the job to `status=error` with the mapped code.
   - `GET /api/jobs/{id}` is owner-only.
   - Jobs left `running` from an earlier process become `error` at startup.
3. **Documents:**
   - `GET /api/documents?q&subject&page` (20 per page, `q` uses `LIKE` on title and content);
   - `GET`, `PATCH` (title, subject) and `DELETE /api/documents/{id}`, owner-only;
   - `GET /api/documents/{id}/export?format=md` returns `.md` text.
4. **Dashboard:** `GET /api/dashboard` with real data:
   - `week`: 7 days of the user's events (empty lists until L5);
   - `next_event`;
   - `stats`: summary count and document count;
   - `recent`: the last 5 documents.
   - Return cut blocks as empty or null to match the contract: `points_ring`, `top5`, `me_row`, `reminders`, `questions_for_you`.
5. **Health and errors:**
   - `/api/health` reports `modelscope: invalid_token` after a 401;
   - AI endpoints then return 503 `modelscope_token_invalid`;
   - any unhandled exception returns the error JSON and never a traceback.
6. **Seed** (`python -m server.seed`, idempotent): 3 subjects, a demo user `demo` / `demo12345`, and 2 sample documents with LaTeX and code.
7. **Tests** (`server/tests/test_api_core.py`):
   - register without terms returns `terms_required`;
   - login with a wrong password returns a generic error;
   - a summary job runs end to end with `FakeLLM` and creates a document;
   - another user's document returns 404;
   - a test asserts the INSERT column lists;
   - any exception returns the error JSON.

## Done when
- [ ] `pytest`, `ruff` and `compliance` pass.
- [ ] Run this flow locally with the real token: start uvicorn with a fresh `DATA_DIR`, then register, upload a small PDF, poll until done, open the document, export it and check the dashboard. Paste the status codes into the report.
- [ ] Deploy to the Studio if the developer has created it, then check `/api/health` there.
