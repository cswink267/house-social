"""The public tree must not carry credentials or a private machine path."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv"}
BANNED = (
    re.compile(r"EAA[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bsk_live_[A-Za-z0-9]{10,}"),
    re.compile(r"access_token=(?!REDACTED)[A-Za-z0-9_\-]{20,}"),
    re.compile("/home/" + "blackthorn"),
)


def test_public_tree_has_no_credentials():
    offenders = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or SKIP.intersection(path.parts):
            continue
        if path.suffix not in {".py", ".js", ".css", ".json", ".yaml", ".yml", ".md", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in BANNED:
            if pattern.search(text):
                offenders.append(f"{path.relative_to(ROOT)} matches {pattern.pattern}")
    assert offenders == []
