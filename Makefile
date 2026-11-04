# Orvina — developer entry points (SPEC §3, §12). One backend process, free CPU.
# Python runs from .venv (uv); web from web/node_modules (npm). No Docker locally.

PY      := .venv/Scripts/python.exe
PIP     := uv pip install -p .venv
WEB_DIR := web

.PHONY: dev test lint build e2e compliance docker

# Run the FastAPI server on 0.0.0.0:7860 (one worker) against a local DATA_DIR.
dev:
	$(PY) -m uvicorn server.main:app --host 0.0.0.0 --port 7860 --workers 1 --reload --env-file .env

# Python unit/contract tests (pytest). Schemathesis is a scope cut.
test:
	$(PY) -m pytest server/tests -q

# Lint: ruff on Python, tsc --noEmit on the generated TS types + mocks,
# and the locale parity check (id/en must stay in sync).
lint:
	$(PY) -m ruff check server scripts
	cd $(WEB_DIR) && npx tsc --noEmit
	cd $(WEB_DIR) && node scripts/check-locales.mjs

# Build: web production bundle (tsc + vite) — what the Docker image serves.
build:
	cd $(WEB_DIR) && npm run build

# Playwright E2E is a scope cut (no recordings, no load tests).
e2e:
	@echo "skipped: scope cut"

# SPEC §12 compliance scan (only 4 models, openai only in server/ai/, no secrets,
# no Web Speech API, no emoji in UI strings, <=30 MANUAL lines).
compliance:
	$(PY) scripts/compliance.py

# No Docker on this machine; the first real image build is the Studio's.
docker:
	@echo "no Docker locally"
