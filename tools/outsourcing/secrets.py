"""Secret detection for file paths and file content.

CAPABILITIES:
  CAP-OUTSOURCING-003: detect secrets in file paths and content [tests: test_FR_1_0_01_mc10_every_outsourcing_module_is_secret_clean, test_FR_1_0_01_mc10_secret_shapes_are_flagged, test_FR_1_0_01_mc10_bare_prefixes_are_clean, test_secrets.py]
INPUTS AND OUTPUTS: secret_reasons(path, text) -> list[str].
CONTRACTS: none.
INVARIANTS:
  - Returns [] for clean files; list of reason strings otherwise.
  - This module's own source code must return [].
NOT IN SCOPE:
  - Masking or removing secrets.
CHANGE LOG:
  2026-10-10 WO-1.0-01 created.
"""
from __future__ import annotations

import re
from pathlib import PurePosixPath

__all__ = ["secret_reasons"]

# Split pattern constants so the detector's own source code is clean
_HF_PAT = re.compile("hf_" + r"[a-zA-Z0-9]{30,}")
_GHP_PAT = re.compile("ghp_" + r"[a-zA-Z0-9]{36}")
_GHP_PAT_PAT = re.compile("github_pat_" + r"[a-zA-Z0-9_]{22,}")
_GOOG_PAT = re.compile("AIza" + r"[a-zA-Z0-9_-]{35}")
_ANT_PAT = re.compile("sk-ant-" + r"[a-zA-Z0-9_-]{20,}")
_KEY_HEADER_PAT = re.compile(r"^\s*-----BEGIN\s+.*PRIVATE\s+KEY-----\s*$", re.MULTILINE)


def secret_reasons(path: str, text: str) -> list[str]:
    """Flag path and text for secret-looking features.

    Returns a list of reasons. Empty list means clean.
    """
    reasons: list[str] = []
    p = PurePosixPath(path)
    name = p.name.lower()

    if name == ".env" or name.endswith(".env"):
        reasons.append(f"Filename {p.name!r} indicates an environment secret file")
    if name.endswith(".pem"):
        reasons.append(f"Filename {p.name!r} indicates a PEM certificate/key")
    if name.endswith(".key"):
        reasons.append(f"Filename {p.name!r} indicates a private key")
    if name.startswith("id_rsa"):
        reasons.append(f"Filename {p.name!r} indicates an SSH key")
    if name.endswith(".p12"):
        reasons.append(f"Filename {p.name!r} indicates a PKCS#12 bundle")

    if _KEY_HEADER_PAT.search(text):
        reasons.append("Content contains a private key header")
    if _HF_PAT.search(text):
        reasons.append("Content contains a Hugging Face token pattern")
    if _GHP_PAT.search(text) or _GHP_PAT_PAT.search(text):
        reasons.append("Content contains a GitHub token pattern")
    if _GOOG_PAT.search(text):
        reasons.append("Content contains a Google API key pattern")
    if _ANT_PAT.search(text):
        reasons.append("Content contains an Anthropic key pattern")

    return reasons
