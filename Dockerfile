# Orvina — 2-stage image (SPEC §13). One process, one port (7860), free CPU.
# Stage 1: build the React app. Stage 2: Python runtime.

FROM node:20-slim AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.10-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# CJK fonts for zh chart rendering (SPEC §10.6).
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY server/requirements.txt ./server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
# whisper pre-download removed: F2 / audio-video input is a scope cut
# (ENABLE_TRANSCRIPTION=false, faster-whisper no longer a dependency).
COPY server/ ./server/
COPY --from=web /app/web/dist /app/web/dist
EXPOSE 7860
# Shell form so ${PORT} expands; one worker, proxy headers from the Studio proxy.
CMD uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1 --proxy-headers --forwarded-allow-ips "*"
