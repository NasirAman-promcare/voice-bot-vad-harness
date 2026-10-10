"""Unit tests for return format bundle parsing.

CAPABILITIES:
  CAP-OUTSOURCING-005: parse RETURN_FORMAT bundle text and check truncation signs [tests: test_FR_1_0_01_parse_valid_bundle, test_FR_1_0_01_truncation_raises_truncated_bundle, test_FR_1_0_01_invalid_bundle_syntax_raises_bundle_error]
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
from tools.outsourcing.bundle import BundleError, TruncatedBundle, parse_bundle


def valid_bundle_text(file_path="tools/demo/alpha.py", file_content="VALUE = 1\n"):
    return f"""=== MANIFEST ===
| path | action | purpose |
| --- | --- | --- |
| {file_path} | create | demo |
=== END MANIFEST ===
=== FILE: {file_path} ===
{file_content.strip()}
=== END FILE ===
=== DOD ===
| item | met at (file:line) | how |
| --- | --- | --- |
| D1 | {file_path}:1 | demo |
=== END DOD ===
"""


def test_FR_1_0_01_parse_valid_bundle():
    bundle = parse_bundle(valid_bundle_text())
    assert len(bundle.manifest) == 1
    assert bundle.manifest[0][0] == "tools/demo/alpha.py"
    assert len(bundle.files) == 1
    assert bundle.files[0][0] == "tools/demo/alpha.py"
    assert bundle.files[0][1] == "VALUE = 1\n"
    assert bundle.questions == ()


@pytest.mark.parametrize("line", [
    "...",
    "…",
    "# ...",
    "   # rest of the file as before",
    "// same as before",
    "# omitted for brevity",
])
def test_FR_1_0_01_truncation_raises_truncated_bundle(line: str):
    text = valid_bundle_text(file_content=f"def foo():\n    return 1\n{line}\n")
    with pytest.raises(TruncatedBundle):
        parse_bundle(text)


def test_FR_1_0_01_invalid_bundle_syntax_raises_bundle_error():
    # Non-blank text outside block
    text_stray = "stray line\n" + valid_bundle_text()
    with pytest.raises(BundleError, match="outside block"):
        parse_bundle(text_stray)

    # Missing END marker
    text_no_end = valid_bundle_text().replace("=== END FILE ===", "")
    with pytest.raises(BundleError):
        parse_bundle(text_no_end)

    # Duplicate file
    text_dup = valid_bundle_text() + "\n=== FILE: tools/demo/alpha.py ===\nVALUE = 2\n=== END FILE ===\n"
    with pytest.raises(BundleError, match="Duplicate"):
        parse_bundle(text_dup)
