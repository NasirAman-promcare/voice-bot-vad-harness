"""Unit tests for tools.index.headers (WO-1.0-03 step 1).

CAPABILITIES:
  none.
INPUTS AND OUTPUTS: pytest tests for the header parser; no I/O beyond in-memory strings.
CONTRACTS: docs/process/CHANGE_CONTROL.md section 1.
INVARIANTS:
  - No network, no sleeps, no randomness, no filesystem use.
NOT IN SCOPE:
  - Scanning, registry and rendering (later steps).
CHANGE LOG:
  2026-10-12 WP-1.0 FR-1.0-03 created.
"""
from __future__ import annotations

import pytest

from tools.index.headers import HEADER_SECTIONS, parse_header

FULL_HEADER = '''"""Alignment and corpus-level WER for normalised transcripts.

CAPABILITIES:
  CAP-SCORE-002: align() is a unit-cost Levenshtein alignment [tests: test_FR_0_3_04_hand_counted_alignments,
    test_FR_0_3_04_tie_break_follows_documented_rule]
  CAP-SCORE-003: corpus_summary() gives per-variant totals [tests: test_FR_0_3_05_corpus_wer_is_total_errors]
INPUTS AND OUTPUTS: token sequences in; Alignment values out.
CONTRACTS: docs/contracts/SCORE_TABLE.md ("Alignment").
INVARIANTS:
  - errors = substitutions + deletions + insertions.
NOT IN SCOPE:
  - Normalising text.
CHANGE LOG:
  2026-09-27 WP-0.3 FR-0.3-04 created.
  2026-09-28 WP-0.3 FR-0.3-05 corpus summary added.
"""'''


def test_FR_1_0_03_parses_a_full_header() -> None:
    header = parse_header(FULL_HEADER)
    assert header.purpose == "Alignment and corpus-level WER for normalised transcripts."
    assert [cap.cap_id for cap in header.capabilities] == ["CAP-SCORE-002", "CAP-SCORE-003"]
    assert header.capabilities[0].description == "align() is a unit-cost Levenshtein alignment"
    assert header.contracts == 'docs/contracts/SCORE_TABLE.md ("Alignment").'
    assert header.change_log == (
        "2026-09-27 WP-0.3 FR-0.3-04 created.",
        "2026-09-28 WP-0.3 FR-0.3-05 corpus summary added.",
    )
    assert header.missing == ()


def test_FR_1_0_03_capability_entries_continue_on_deeper_lines() -> None:
    docstring = (
        '"""Purpose line.\n\nCAPABILITIES:\n'
        "  CAP-A-001: does the first thing and\n"
        "    continues onto a deeper line [tests: test_one]\n"
        "  CAP-A-002: does the second thing [tests: test_two]\n"
        "INPUTS AND OUTPUTS: x in, y out.\nCONTRACTS: none.\nINVARIANTS:\n  - none.\n"
        "NOT IN SCOPE:\n  - nothing.\nCHANGE LOG:\n  2026-10-10 WP-9.1 FR-9.1-01 created.\n\"\"\""
    )
    header = parse_header(docstring)
    assert header.capabilities[0].description == "does the first thing and continues onto a deeper line"
    assert header.capabilities[0].tests == ("test_one",)
    assert header.capabilities[1].description == "does the second thing"


def test_FR_1_0_03_tests_may_span_continuation_lines_and_keep_order() -> None:
    docstring = (
        '"""Purpose.\n\nCAPABILITIES:\n'
        "  CAP-B-001: text [tests: test_first,\n"
        "    test_second, test_third]\n"
        "INPUTS AND OUTPUTS: x.\nCONTRACTS: none.\nINVARIANTS:\n  - i.\n"
        "NOT IN SCOPE:\n  - n.\nCHANGE LOG:\n  2026-10-10 WP-9.1 FR-9.1-01 created.\n\"\"\""
    )
    header = parse_header(docstring)
    assert header.capabilities[0].tests == ("test_first", "test_second", "test_third")
    assert header.missing == ()


def test_FR_1_0_03_missing_sections_are_listed() -> None:
    docstring = (
        '"""Purpose only.\n\nCAPABILITIES:\n  none.\n'
        "CHANGE LOG:\n  2026-10-10 WP-9.1 FR-9.1-01 created.\n\"\"\""
    )
    header = parse_header(docstring)
    assert header.purpose == "Purpose only."
    assert header.missing == ("INPUTS AND OUTPUTS", "CONTRACTS", "INVARIANTS", "NOT IN SCOPE")
    assert header.capabilities == ()
    assert header.contracts == ""


def test_FR_1_0_03_purpose_is_the_first_line() -> None:
    header = parse_header(FULL_HEADER)
    assert header.purpose == FULL_HEADER.splitlines()[0].strip('"')


def test_FR_1_0_03_no_capabilities_gives_an_empty_list() -> None:
    docstring = (
        '"""Purpose.\n\nCAPABILITIES:\n  none.\nINPUTS AND OUTPUTS: x.\nCONTRACTS: none.\n'
        "INVARIANTS:\n  - i.\nNOT IN SCOPE:\n  - n.\n"
        "CHANGE LOG:\n  2026-10-10 WP-9.1 FR-9.1-01 created.\n\"\"\""
    )
    assert parse_header(docstring).capabilities == ()


def test_FR_1_0_03_a_docstring_without_any_section_is_purpose_only() -> None:
    header = parse_header('"""Just a sentence.\n\nMore detail here.\n"""')
    assert header.purpose == "Just a sentence."
    assert header.missing == HEADER_SECTIONS


def test_FR_1_0_03_change_log_entries_are_kept_verbatim() -> None:
    docstring = (
        '"""Purpose.\n\nCAPABILITIES:\n  none.\nINPUTS AND OUTPUTS: x.\nCONTRACTS: none.\n'
        "INVARIANTS:\n  - i.\nNOT IN SCOPE:\n  - n.\n"
        "CHANGE LOG:\n"
        "  2026-09-25 WP-0.0 FR-0.0-05 created.\n"
        "  2026-09-25 WP-0.0 round 2 FR-0.0-06 (amended), F04, F09: Stop hook v2/v3 scan scope;\n"
        "             fail closed.\n\"\"\""
    )
    header = parse_header(docstring)
    assert header.change_log == (
        "2026-09-25 WP-0.0 FR-0.0-05 created.",
        "2026-09-25 WP-0.0 round 2 FR-0.0-06 (amended), F04, F09: Stop hook v2/v3 scan scope;",
        "fail closed.",
    )


@pytest.mark.parametrize("docstring", [None, "", '"""   \n"""'])
def test_FR_1_0_03_empty_docstring_reports_every_section(docstring: str | None) -> None:
    header = parse_header(docstring)
    assert header.purpose == ""
    assert header.missing == HEADER_SECTIONS
    assert header.capabilities == ()
