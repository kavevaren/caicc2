"""Shared fixtures: a fresh throwaway DATA_DIR and a TestClient for the app.

The DATA_DIR env var must be set BEFORE `server.config` is imported (it reads it
at import time), so we set it at module import here — pytest imports conftest
before any test module, which happens before `server.main`.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Project root on sys.path so `import server...` works regardless of cwd.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Fresh empty data dir for every test run (no secrets, no real token).
_TMP = tempfile.mkdtemp(prefix="orvina-test-")
os.environ["DATA_DIR"] = _TMP
os.environ.pop("MODELSCOPE_TOKEN", None)
os.environ.pop("APP_SECRET_KEY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from server.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    # Context manager runs the lifespan: migrations + seed + probe thread.
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return Path(_TMP)
