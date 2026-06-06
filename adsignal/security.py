"""
Agentic-security utilities — ECC integration.

Ported from the ECC operator system's ``scripts/ci/check-unicode-safety.js``
(https://github.com/affaan-m/ecc, MIT). ECC's security guide details how
"ASCII smuggling" / invisible-Unicode prompt injection works: an attacker hides
instructions inside otherwise-ASCII-looking text (PR bodies, docs, or — in our
case — ad creative copy fetched from external sources). A human reviewer sees
nothing; the LLM consumes the hidden tag/format bytes as instructions.

AdSignal is a textbook "lethal trifecta" target: it ingests untrusted external
text (Meta Ad Library / scraped creatives), holds private data, and forwards
that text into an LLM narrative engine. This module provides:

* :func:`sanitize_external_text` — strip dangerous invisible code points from any
  externally-sourced string before it is stored or sent to the LLM (runtime
  defense, wired into the ingest path and the prompt builder).
* :func:`scan_text` / :func:`scan_path` — detect violations for the CI gate
  (see ``scripts/ecc_security_scan.py`` and ``make security``).

See ECC_USAGE.md for the full integration story.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

# Text file extensions worth scanning in the repo (mirrors ECC's set, trimmed
# to what AdSignal actually contains).
TEXT_EXTENSIONS = {
    ".py", ".md", ".mdx", ".txt", ".json", ".toml", ".yml", ".yaml",
    ".sh", ".bash", ".zsh", ".cfg", ".ini", ".js", ".ts",
}

IGNORED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".web", ".states",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", ".dagster", "assets",
}


def is_dangerous_invisible(code_point: int) -> bool:
    """True for invisible/format code points abused for Unicode smuggling.

    Faithful port of ECC's ``isDangerousInvisibleCodePoint``. These ranges carry
    no legitimate meaning in source code or ad copy and are the canonical vectors
    for hidden-instruction prompt injection and homograph attacks.
    """
    return (
        # Zero-width space / joiner / non-joiner, word joiner, BOM.
        (0x200B <= code_point <= 0x200D)
        or code_point == 0x2060
        or code_point == 0xFEFF
        # Bidirectional overrides/embeddings (Trojan Source — CVE-2021-42574).
        or (0x202A <= code_point <= 0x202E)
        or (0x2066 <= code_point <= 0x2069)
        # Variation selectors.
        or (0xFE00 <= code_point <= 0xFE0F)
        or (0xE0100 <= code_point <= 0xE01EF)
        # Unicode Tag block — the canonical "ASCII smuggling" vector.
        or (0xE0000 <= code_point <= 0xE007F)
        # Mongolian vowel separator (renders zero-width).
        or code_point == 0x180E
        # Hangul fillers abused as invisible characters.
        or code_point == 0x115F
        or code_point == 0x1160
        # Invisible math operators.
        or (0x2061 <= code_point <= 0x2064)
        # Hangul filler used in chat-app smuggling.
        or code_point == 0x3164
    )


@dataclass(frozen=True)
class Violation:
    """A single dangerous code point located in a file."""

    file: str
    line: int
    column: int
    code_point: str


def sanitize_external_text(text: str) -> str:
    """Strip dangerous invisible code points from untrusted text.

    Apply to any externally-sourced string (ad copy, CTAs, themes) before it is
    persisted or forwarded to the LLM. Visible characters are untouched, so the
    cleaned text is identical to what a human sees — only the smuggled bytes go.
    """
    if not text:
        return text
    return "".join(ch for ch in text if not is_dangerous_invisible(ord(ch)))


def scan_text(text: str) -> list[tuple[int, int, str]]:
    """Return ``(line, column, code_point)`` for each dangerous char in ``text``."""
    hits: list[tuple[int, int, str]] = []
    line = 1
    column = 1
    for ch in text:
        if ch == "\n":
            line += 1
            column = 1
            continue
        if is_dangerous_invisible(ord(ch)):
            hits.append((line, column, f"U+{ord(ch):04X}"))
        column += 1
    return hits


def _is_text_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in TEXT_EXTENSIONS


def scan_path(root: str) -> list[Violation]:
    """Recursively scan ``root`` for dangerous invisible Unicode in text files."""
    violations: list[Violation] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for name in filenames:
            full = os.path.join(dirpath, name)
            if not _is_text_file(full):
                continue
            try:
                with open(full, encoding="utf-8") as fh:
                    text = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            rel = os.path.relpath(full, root)
            for line, column, cp in scan_text(text):
                violations.append(Violation(file=rel, line=line, column=column, code_point=cp))
    return violations
