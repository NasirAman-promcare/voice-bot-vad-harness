"""Parse the module header standard (CHANGE_CONTROL.md section 1) into a Header record.

CAPABILITIES:
  CAP-INDEX-001: parse_header() reads a module docstring into purpose, capabilities (ID, description,
  tests), contracts and change-log entries, reporting missing sections without guessing them
  [tests: test_FR_1_0_03_parses_a_full_header, test_FR_1_0_03_capability_entries_continue_on_deeper_lines,
  test_FR_1_0_03_tests_may_span_continuation_lines_and_keep_order, test_FR_1_0_03_missing_sections_are_listed,
  test_FR_1_0_03_purpose_is_the_first_line, test_FR_1_0_03_no_capabilities_gives_an_empty_list,
  test_FR_1_0_03_a_docstring_without_any_section_is_purpose_only, test_FR_1_0_03_change_log_entries_are_kept_verbatim,
  test_FR_1_0_03_empty_docstring_reports_every_section]
INPUTS AND OUTPUTS: a module docstring (or None) in; a Header value out. Never raises on content.
CONTRACTS: docs/process/CHANGE_CONTROL.md section 1; registry columns per tools.audit.gate.
INVARIANTS:
  - Pure text parsing; no I/O, no clock, no environment reads.
  - Missing sections are listed in Header.missing, never invented.
NOT IN SCOPE:
  - Scanning files (scan.py) and building the registry (registry.py).
CHANGE LOG:
  2026-10-12 WP-1.0 FR-1.0-03 created.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["Capability", "Header", "parse_header", "HEADER_SECTIONS"]

#: The sections of CHANGE_CONTROL.md section 1, in order. CAPABILITIES entries are parsed separately.
HEADER_SECTIONS: tuple[str, ...] = (
    "CAPABILITIES",
    "INPUTS AND OUTPUTS",
    "CONTRACTS",
    "INVARIANTS",
    "NOT IN SCOPE",
    "CHANGE LOG",
)

_SECTION_RE = re.compile(r"^([A-Z][A-Z ]*[A-Z]):[ \t]?(.*)$")
_CAP_START_RE = re.compile(r"^\s+(CAP-[A-Z0-9-]+):\s*(.*)$")
_TESTS_RE = re.compile(r"\[tests:(.*?)\]", re.S)


@dataclass(frozen=True)
class Capability:
    """One CAPABILITIES entry: its ID, description (without the tests part) and test names in order."""

    cap_id: str
    description: str
    tests: tuple[str, ...] = ()


@dataclass(frozen=True)
class Header:
    """A parsed module header: purpose line, capabilities, section bodies and what is missing."""

    purpose: str
    capabilities: tuple[Capability, ...] = ()
    contracts: str = ""
    change_log: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


def _strip_quotes(text: str) -> str:
    """Remove a leading and trailing triple-quote delimiter, when present.

    Callers may hand us the raw docstring source (including the quotes) or an already-clean
    docstring; either way the parser must see only the content. Quotes are stripped only at
    the very start and very end so a quote inside the text stays untouched.
    """
    stripped = text.strip()
    for delimiter in ('"""', "'''"):
        if stripped.startswith(delimiter) and stripped.endswith(delimiter) and len(stripped) >= 2 * len(delimiter):
            return stripped[len(delimiter):-len(delimiter)]
    return text


def _split_sections(docstring: str) -> tuple[str, dict[str, list[str]], list[str]]:
    """(purpose, {section: body lines}, missing) for a docstring's raw text.

    A section starts at an unindented ALL-CAPS label ending in ':'; everything up to the next such
    label is its body. Lines before the first label form the purpose block (its first line is the
    purpose). Sections that never appear are reported in `missing`.
    """
    lines = docstring.split("\n")
    purpose_lines: list[str] = []
    bodies: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        match = _SECTION_RE.match(line)
        if match and match.group(1) in HEADER_SECTIONS:
            current = match.group(1)
            if current not in bodies:
                bodies[current] = []
            if match.group(2).strip():
                bodies[current].append(match.group(2).strip())
            continue
        if current is None:
            purpose_lines.append(line)
        else:
            bodies[current].append(line)
    purpose = ""
    for line in purpose_lines:
        if line.strip():
            purpose = line.strip()
            break
    missing = [name for name in HEADER_SECTIONS if name not in bodies]
    return purpose, bodies, missing


def _is_entry_start(line: str) -> bool:
    """True when an indented line starts a new CAP- entry rather than continuing the previous one."""
    return bool(_CAP_START_RE.match(line))


def _parse_capabilities(body: list[str]) -> tuple[Capability, ...]:
    """Capabilities of a CAPABILITIES body; continuation lines join with single spaces."""
    entries: list[tuple[str, str]] = []
    for line in body:
        if not line.strip():
            continue
        match = _CAP_START_RE.match(line)
        if match:
            entries.append((match.group(1), match.group(2).strip()))
        elif entries:
            cap_id, text = entries[-1]
            entries[-1] = (cap_id, text + " " + line.strip())
        # text before the first CAP- line is prose such as "none."; it is not an entry
    capabilities: list[Capability] = []
    for cap_id, text in entries:
        tests: tuple[str, ...] = ()
        match = _TESTS_RE.search(text)
        if match:
            tests = tuple(part.strip().strip("`") for part in match.group(1).split(",") if part.strip())
        description = _TESTS_RE.sub("", text).strip()
        capabilities.append(Capability(cap_id=cap_id, description=description, tests=tests))
    return tuple(capabilities)


def _single_line(body: list[str]) -> str:
    return " ".join(line.strip() for line in body if line.strip())


def parse_header(docstring: str | None) -> Header:
    """Parse a module docstring per CHANGE_CONTROL.md section 1.

    None or a docstring without sections yields an empty purpose and every section listed missing;
    nothing is guessed. Never raises: a malformed header is a Header with missing sections.
    Accepts the raw source text (with triple quotes) or a cleaned docstring.
    """
    if docstring is None:
        return Header(purpose="", missing=HEADER_SECTIONS)
    content = _strip_quotes(docstring)
    if not content.strip():
        return Header(purpose="", missing=HEADER_SECTIONS)
    purpose, bodies, missing = _split_sections(content)
    capabilities = _parse_capabilities(bodies.get("CAPABILITIES", []))
    contracts = _single_line(bodies.get("CONTRACTS", []))
    change_log = tuple(
        line.strip() for line in bodies.get("CHANGE LOG", []) if line.strip())
    return Header(purpose=purpose, capabilities=capabilities, contracts=contracts,
                  change_log=change_log, missing=tuple(missing))
