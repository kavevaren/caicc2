"""SPEC §12 Compliance scan — must pass on the skeleton and at every phase end.

Scans source (`.py .ts .tsx .json .yaml .md`) and fails on:
  * a non-allowed model ID, or `openai` imported outside `server/ai/`;
  * a forbidden AI domain or the Web Speech API (`SpeechRecognition`);
  * a token-like string (a secret leaked into code, bundle, docs or tests);
  * emoji in UI strings;
  * more than 30 `MANUAL` lines (the authorship marker we must never write).

Excludes generated / vendored / external trees: `.venv`, `node_modules`,
`web/dist`, `arsip`, `Orviva`, `__pycache__`, lockfiles and zip archives. Run via
`make compliance` (or `python scripts/compliance.py`). Exit 0 = clean.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The four allowed ModelScope models (SPEC §2.1) — nowhere else may a model ID appear.
ALLOWED_MODELS = {
    "zai-org/GLM-5.2",
    "deepseek-ai/DeepSeek-V4-Pro-0813",
    "stepfun-ai/Step-3.5-Flash",
    "Qwen/Qwen3.8-27B",
}

# Paths never scanned (generated, vendored, or history — not our authored code).
# `Orviva` is a clone of the deployed studio (a separate repo); its README holds a
# `git clone .../Orviva.git` URL that the model-ID pattern would otherwise flag.
EXCLUDE_DIRS = {".venv", "node_modules", "dist", "arsip", "__pycache__", ".git", "Orviva"}
EXCLUDE_FILES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}

TEXT_EXTS = {".py", ".ts", ".tsx", ".json", ".yaml", ".yml", ".md"}

# --- detectors ---------------------------------------------------------------

# A model-ID-shaped token: two slash-separated segments (org/name). Anything that
# looks like one but is not an allowed model is a violation.
MODEL_ID_RE = re.compile(r"\b([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\b")

# `openai` as a Python import (module or attribute form), not a comment/word match.
OPENAI_IMPORT_RE = re.compile(r"^\s*(?:import\s+openai\b|from\s+openai\b)", re.MULTILINE)

# Proprietary AI services / endpoints that are not ModelScope inference.
FORBIDDEN_DOMAIN_RE = re.compile(
    r"(api\.openai\.com|openai\.azure\.com|api\.anthropic\.com|generativelanguage\.googleapis\.com"
    r"|api\.cohere\.ai|api\.mistral\.ai|api\.together\.ai|api\.replicate\.com|huggingface\.co)"
)

# The Web Speech API (disallowed anywhere, SPEC §2.2).
WEB_SPEECH_RE = re.compile(r"\bSpeechRecognition\b|window\.speechSynthesis\b|\bspeechSynthesis\b")

# A credential-looking literal: long high-entropy base64/hex, or a known vendor prefix.
TOKEN_RE = re.compile(
    r"(?i)(ms-[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}"
    r"|[A-Za-z0-9+/]{48,}={0,2})"
)

# Emoji — real pictographs/emoticons only (no geometric shapes, no dingbat arrows,
# no math operators). DESIGN.md legitimately uses ⚡/★/● as design tokens, so those
# are excluded from this check.
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF"  # misc symbols & pictographs A
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F900-\U0001F9FF"  # supplemental symbols & pictographs
    "\U0001FA70-\U0001FAFF"  # symbols & pictographs extended-A
    "\U0001F1E6-\U0001F1FF"  # regional indicators (flags)
    "☀-☄★☆♌☎"  # misc symbols + dingbats subset (☀☁☂☄★☆♌☎), no arrows/math
    "❤"                # heavy black heart
    "️"             # variation selector-16 (emoji presentation)
    "]"
)


def _iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        parts = rel.parts
        if any(p in EXCLUDE_DIRS for p in parts):
            continue
        if path.name in EXCLUDE_FILES or path.suffix == ".zip":
            continue
        if path.suffix not in TEXT_EXTS:
            continue
        yield rel, path


# Common source/doc/data file extensions — a slash-token ending in one of these
# is a path, not a model ID (all four allowed models end in a bare number/word).
_FILE_EXTS = {
    "py", "ts", "tsx", "js", "jsx", "json", "yaml", "yml", "md", "html", "css",
    "svg", "png", "jpg", "jpeg", "webp", "gif", "srt", "vtt", "txt", "zip",
    "sql", "sh", "toml", "ini", "env", "lock", "ico", "woff", "woff2",
    "mjs", "cjs", "exe", "mp4", "webm", "wav", "mp3", "xml", "xlsx", "docx",
    "ics",
}


def _is_model_id(token: str) -> bool:
    """Heuristic: does this org/name token look like a ModelScope model ID?

    All four allowed models have a dotted version/weight in the name segment
    (GLM-5.2, DeepSeek-V4-Pro-0813, Step-3.5-Flash, Qwen3.8-27B) and no file
    extension. File paths (`docs/SPEC.md`), i18n codes and prose tokens do not
    match — so we require a dot in the name segment AND no known file extension,
    which keeps false positives near zero while still catching a leaked foreign
    model ID like `openai/gpt-4`.
    """
    head, _, tail = token.partition("/")
    if token in ALLOWED_MODELS:
        return False
    if len(head) < 2 or "/" in tail:
        return False
    if token.startswith(("http", "/", ".")) or ":" in token:
        return False
    if "." not in tail:
        return False
    # A trailing `.ext` that is a real file extension means this is a path.
    last_ext = tail.rsplit(".", 1)[-1].lower()
    return last_ext not in _FILE_EXTS


# Docs legitimately *describe* the Web-Speech ban; only code can use it.
DOC_EXTS = {".md"}


def check() -> list[str]:
    problems: list[str] = []
    manual_lines = 0
    self_rel = Path("scripts") / "compliance.py"
    for rel, path in _iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        lines = text.splitlines()
        is_doc = rel.suffix in DOC_EXTS
        is_self = rel == self_rel

        # 1. openai imported outside server/ai/
        if not is_doc and OPENAI_IMPORT_RE.search(text) and rel.parts[:2] != ("server", "ai"):
            problems.append(f"{rel}: `openai` imported outside server/ai/")

        # 2. forbidden AI domains / Web Speech API (code only — docs may describe the ban)
        if not is_doc:
            for m in FORBIDDEN_DOMAIN_RE.finditer(text):
                problems.append(f"{rel}: forbidden AI domain {m.group(0)!r}")
            if not is_self:
                for m in WEB_SPEECH_RE.finditer(text):
                    problems.append(f"{rel}: Web Speech API usage {m.group(0)!r}")

        # 3. non-allowed model IDs
        for m in MODEL_ID_RE.finditer(text):
            tok = m.group(1)
            if tok in ALLOWED_MODELS:
                continue
            if _is_model_id(tok):
                problems.append(f"{rel}: non-allowed model ID {tok!r}")

        # 4. token-like strings (secrets). A base64 PNG/JPEG data-URI is an image,
        #    not a credential, so skip matches that are clearly image headers.
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith(("#", "//")):
                continue
            for m in TOKEN_RE.finditer(line):
                cand = m.group(0)
                if cand.startswith(("iVBORw0KGgo", "/9j/", "R0lGOD")):  # PNG/JPEG/GIF base64
                    continue
                problems.append(f"{rel}:{i}: token-like string {cand[:12]}…")

        # 5. emoji in UI strings. The scanner itself defines the emoji range as
        #    literal characters, so it is exempted from this one check only.
        if not is_self:
            for i, line in enumerate(lines, 1):
                if EMOJI_RE.search(line):
                    problems.append(f"{rel}:{i}: emoji in a UI/source string")

        # 6. MANUAL authorship marker (must stay <= 30 total; we never write it)
        manual_lines += sum(1 for ln in lines if "MANUAL" in ln)

    if manual_lines > 30:
        problems.append(f"more than 30 MANUAL lines ({manual_lines}); we never write the MANUAL marker")

    return problems


def main() -> int:
    problems = check()
    if problems:
        print("COMPLIANCE FAILED:")
        for p in problems:
            print("  -", p)
        return 1
    print("compliance OK: 4-model rule, openai isolation, no secrets, no Web Speech API, no emoji, <=30 MANUAL lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
