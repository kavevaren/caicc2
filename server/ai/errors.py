"""AI error types (SPEC §7). Kept in their own module so llm.py / probe.py can
import them without a cycle through the package __init__."""
from __future__ import annotations


class AIError(Exception):
    """AI pipeline failure with a translated code (SPEC §7)."""

    def __init__(self, code: str, params: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.params = params or {}


class ModelScopeAuthError(Exception):
    """401 from ModelScope: bad or missing token. Never retried (SPEC §9.1)."""
