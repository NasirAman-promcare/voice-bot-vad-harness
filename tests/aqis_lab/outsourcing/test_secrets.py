"""Unit tests for secret detection.

CAPABILITIES:
  CAP-OUTSOURCING-003: detect secrets in file paths and content [tests: test_FR_1_0_01_secret_path_detection, test_FR_1_0_01_secret_content_detection, test_FR_1_0_01_clean_content]
INPUTS AND OUTPUTS: pytest tests.
CONTRACTS: none.
INVARIANTS:
  - All tests pass cleanly.
NOT IN SCOPE:
  - Acceptance tests (see test_acceptance_wo_1_0_01.py).
CHANGE LOG:
  2026-10-10 WO-1.0-01 created.
"""
from __future__ import annotations

import pytest
from tools.outsourcing.secrets import secret_reasons

KEY_HEADER = "-----BEGIN " + "RSA PRIVATE KEY-----"


@pytest.mark.parametrize("path", [
    ".env",
    "config/.env",
    "server.pem",
    "cert.key",
    "id_rsa",
    "id_rsa.pub",
    "home/id_rsa_test",
    "keystore.p12",
])
def test_FR_1_0_01_secret_path_detection(path: str):
    reasons = secret_reasons(path, "clean content\n")
    assert len(reasons) > 0


@pytest.mark.parametrize("text", [
    f"Header:\n{KEY_HEADER}\ndata\n",
    "token = " + "hf_" + "A" * 30,
    "token = " + "ghp_" + "B" * 36,
    "token = " + "github_pat_" + "C" * 25,
    "key = " + "AIza" + "D" * 35,
    "key = " + "sk-ant-" + "E" * 22,
])
def test_FR_1_0_01_secret_content_detection(text: str):
    reasons = secret_reasons("clean_file.py", text)
    assert len(reasons) > 0


def test_FR_1_0_01_clean_content():
    bare = "prefixes hf_ ghp_ github_pat_ AIza sk-ant- -----BEGIN"
    assert secret_reasons("tools/outsourcing/secrets.py", bare) == []
