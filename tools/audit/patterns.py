"""Pattern tables and scan scope for the audit gate's compromise scan (check c) and header check (check d).

CAPABILITIES:
  CAP-AUDIT-008: the compromise, test-integrity, audit-allow (with reason capture) and CAPABILITIES-header patterns, the lab scan scope (directories, suffixes, CI files) and the glob conversion, identical to .claude/hooks/stop_gate.py version 2/3 [tests: test_FR_0_0_06_pattern_tables_identical_to_stop_hook, test_FR_0_0_06_parity_with_stop_hook_on_fixture_repos, test_FR_0_0_06_path_classification_identical_to_hook]
INPUTS AND OUTPUTS: constants plus glob_to_regex(pattern) -> compiled regular expression.
CONTRACTS: labels, regular expressions and scope must stay identical to the Stop hook (FR-0.0-06 amended).
INVARIANTS:
  - This file legitimately contains forbidden words; it is exempted by the owner approval
    'ALLOW-PATTERNS-IN: tools/audit/patterns.py' (docs/approvals/WP-0.0.md).
  - Order matters: the first matching pattern on a line is the one reported.
NOT IN SCOPE:
  - Deciding which changed lines are read, or reporting (tools/audit/gate.py).
CHANGE LOG:
  2026-09-25 WP-0.0 FR-0.0-05 created (copied from .claude/hooks/stop_gate.py).
  2026-09-25 WP-0.0 round 2 FR-0.0-06 (amended): Stop hook v2 tables (shell pattern, skip regex without '@'),
             scan scope constants and glob_to_regex moved here; ALLOW_REASON_RE listed (F06).
"""
import re


def glob_to_regex(pattern):
    """Convert a repo-relative glob with **, * and ? into an anchored regular expression (as the hooks do)."""
    pattern = pattern.strip().lstrip("/")
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            if pattern[i:i + 3] == "**/":
                out.append("(?:.*/)?")
                i += 3
                continue
            if pattern[i:i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


LAB_CODE_DIRS = ("aqis_lab/", "tools/", "config/aqis_lab/", "requirements/aqis_lab/")
LAB_CI_FILES = glob_to_regex(".github/workflows/aqis-lab-*.yml")
LAB_TEST_DIR = "tests/aqis_lab/"
SCANNED_SUFFIXES = (".py", ".sh", ".bash", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".in")

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
    ("errors silenced in shell", re.compile(r"\|\|\s*true\b|2>\s*/dev/null")),
]
TEST_PATTERNS = [
    ("test skip", re.compile(r"pytest\.skip\(|pytest\.mark\.skip(?:if)?\b|unittest\.skip|pytest\.importorskip\(")),
    ("expected-failure marker", re.compile(r"\bxfail\b")),
    ("trivial assertion", re.compile(r"\bassert\s+(?:True|1)\s*(?:#.*)?$")),
]
ALLOW_RE = re.compile(r"#\s*audit-allow:\s*\S")
ALLOW_REASON_RE = re.compile(r"#\s*audit-allow:\s*(\S.*)$")
HEADER_RE = re.compile(r"^\s*CAPABILITIES:", re.M)
