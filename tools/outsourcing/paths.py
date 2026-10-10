"""Path normalisation and classification against protected paths.

CAPABILITIES:
  CAP-OUTSOURCING-002: normalise and classify repository-relative paths [tests: test_FR_1_0_01_mc07_classify_follows_protected_paths, test_paths.py]
INPUTS AND OUTPUTS: normalise(path) -> str, classify(path, repo_root) -> "NEVER" | "GUARDED" | "LAB-OWNED" | "FREE".
CONTRACTS: PROTECTED_PATHS.txt rules.
INVARIANTS:
  - Rejects absolute paths, backslashes and parent directory navigation.
NOT IN SCOPE:
  - Modifying PROTECTED_PATHS.txt.
CHANGE LOG:
  2026-10-10 WO-1.0-01 created.
"""
from __future__ import annotations

from pathlib import Path, PureWindowsPath
from tools.audit.gate import load_protected

__all__ = ["normalise", "classify"]


def normalise(path: str | Path) -> str:
    """Normalise a repository-relative path string.

    Rejects absolute paths, backslashes, empty paths and '..' components.
    Strips leading './' and trailing slashes/whitespace.
    """
    raw = str(path).strip()
    if not raw:
        raise ValueError("Empty path is not allowed")
    if "\\" in raw:
        raise ValueError(f"Path contains backslashes: {raw!r}")
    if raw.startswith("/") or PureWindowsPath(raw).is_absolute() or Path(raw).is_absolute():
        raise ValueError(f"Absolute path is not allowed: {raw!r}")

    # Strip leading ./
    while raw.startswith("./"):
        raw = raw[2:].lstrip()

    raw = raw.rstrip("/")
    if not raw:
        raise ValueError("Empty path after normalisation")

    parts = raw.split("/")
    if ".." in parts:
        raise ValueError(f"Parent directory '..' is not allowed: {raw!r}")
    if "." in parts:
        parts = [p for p in parts if p and p != "."]

    out = "/".join(parts)
    if not out:
        raise ValueError("Empty path after normalisation")
    return out


def classify(path: str | Path, repo_root: str | Path) -> str:
    """Classify a path against PROTECTED_PATHS.txt in repo_root.

    Returns 'NEVER', 'LAB-OWNED', 'GUARDED', or 'FREE'.
    """
    norm = normalise(path)
    sections = load_protected(repo_root)
    if any(rx.match(norm) for rx in sections["NEVER"]):
        return "NEVER"
    if any(rx.match(norm) for rx in sections["LAB-OWNED"]):
        return "LAB-OWNED"
    if any(rx.match(norm) for rx in sections["GUARDED"]):
        return "GUARDED"
    return "FREE"
