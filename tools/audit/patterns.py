"""Pattern tables for the audit gate's compromise scan (check c) and header check (check d).

CAPABILITIES:
  CAP-AUDIT-008: the compromise, test-integrity, audit-allow and CAPABILITIES-header patterns, identical to .claude/hooks/stop_gate.py [tests: test_FR_0_0_06_pattern_tables_identical_to_stop_hook, test_FR_0_0_05_c_detects_each_code_pattern, test_FR_0_0_05_c_detects_each_test_pattern]
INPUTS AND OUTPUTS: constants only.
CONTRACTS: labels and regular expressions must stay byte-identical to the Stop hook (FR-0.0-06).
INVARIANTS:
  - This file legitimately contains forbidden words; it is exempted by the owner approval
    'ALLOW-PATTERNS-IN: tools/audit/patterns.py' (docs/approvals/WP-0.0.md).
  - Order matters: the first matching pattern on a line is the one reported.
NOT IN SCOPE:
  - Deciding which files or lines are scanned (tools/audit/gate.py).
CHANGE LOG:
  2026-09-25 WP-0.0 FR-0.0-05 created (copied from .claude/hooks/stop_gate.py).
"""
import re

CODE_PATTERNS = [
    ("TODO/FIXME/XXX marker", re.compile(r"\b(?:TODO|FIXME|XXX)\b")),
    ("placeholder wording", re.compile(r"\bplaceholders?\b", re.I)),
    ("simplification wording", re.compile(r"\bsimplif(?:y|ied|ies|ying|ication)\b", re.I)),
    ("'for now' wording", re.compile(r"\bfor now\b", re.I)),
    ("temporary wording", re.compile(r"\btemporar(?:y|ily)\b", re.I)),
    ("hack wording", re.compile(r"\bhack(?:s|y|ish)?\b", re.I)),
    ("dummy or fake wording", re.compile(r"\b(?:dummy|fake)\b", re.I)),
    ("NotImplementedError", re.compile(r"\bNotImplementedError\b")),
    ("swallowed exception", re.compile(r"\bexcept\b[^:]*:\s*(?:pass|\.\.\.)\s*(?:#.*)?$")),
    ("bare except", re.compile(r"^\s*except\s*:")),
    ("type-check suppression", re.compile(r"#\s*type:\s*ignore")),
    ("mocking in production code", re.compile(r"\b(?:unittest\.mock|MagicMock|mock\.patch)\b")),
]
TEST_PATTERNS = [
    ("test skip", re.compile(r"pytest\.skip\(|@pytest\.mark\.skip(?:if)?\b|unittest\.skip|pytest\.importorskip\(")),
    ("expected-failure marker", re.compile(r"\bxfail\b")),
    ("trivial assertion", re.compile(r"\bassert\s+(?:True|1)\s*(?:#.*)?$")),
]
ALLOW_RE = re.compile(r"#\s*audit-allow:\s*\S")
ALLOW_REASON_RE = re.compile(r"#\s*audit-allow:\s*(\S.*)$")
HEADER_RE = re.compile(r"^\s*CAPABILITIES:", re.M)
