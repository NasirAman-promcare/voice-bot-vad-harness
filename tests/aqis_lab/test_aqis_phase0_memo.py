"""WP-0.9: the Phase 0 memo (docs/progress/PHASE0_MEMO.md) and the phase 0 debt rows.

FR-0.9-01: exit criteria E1 to E6 with evidence that exists (must-catch 1), decisions quoted from the approvals,
open issues and lessons tied to records; every phase 0 debt row closed or moved with approval (must-catch 2).
FR-0.9-02: the phase 1 prerequisites from their sources. FR-0.9-03: the memo links the phase audit report.
"""
import re
import shutil

import pytest

from aqis_memo_testutil import (DEBT, MEMO, PENDING_LINE, PHASE_AUDIT, SECTIONS, collected_test_names, debt_problems, exit_criteria_problems,
                                lesson_problems, memo_problems, open_issue_problems, phase_audit_problems,
                                prerequisite_problems, quote_problems, read, sections, unit_log_problems)


@pytest.fixture(scope="module")
def tests():
    return collected_test_names()


@pytest.fixture(scope="module")
def memo():
    return read(MEMO)


def test_FR_0_9_01_memo_has_every_section(memo):
    assert list(sections(memo)) == SECTIONS


def test_FR_0_9_01_exit_criteria_link_evidence_that_exists(memo, tests):
    # Must-catch 1.
    assert exit_criteria_problems(memo, tests) == []


def _replace_in_row(memo, row_id, old, new):
    lines = memo.split("\n")
    i = next(i for i, l in enumerate(lines) if l.startswith(f"| {row_id} |"))
    assert old in lines[i], (row_id, old)
    lines[i] = lines[i].replace(old, new, 1)
    return "\n".join(lines)


def _first_span(memo, row_id, kind):
    line = next(l for l in memo.split("\n") if l.startswith(f"| {row_id} |"))
    evidence = line.split(" | ")[3]
    spans = re.findall(r"`([^`]+)`", evidence)
    if kind == "test":
        return next(s for s in spans if s.startswith("test_"))
    if kind == "commit":
        return next(s for s in spans if re.fullmatch(r"[0-9a-f]{7,40}", s))
    return next(s for s in spans if "/" in s)


EVIDENCE_BREAKS = {
    "renamed-path": (lambda m: _replace_in_row(m, "E4", _first_span(m, "E4", "path"),
                                               _first_span(m, "E4", "path").replace("SUMMARY", "SUMMARY_OLD")),
                     "does not exist"),
    "unknown-test": (lambda m: _replace_in_row(m, "E2", _first_span(m, "E2", "test"),
                                               _first_span(m, "E2", "test") + "_renamed"), "is not collected"),
    "unknown-commit": (lambda m: _replace_in_row(m, "E1", _first_span(m, "E1", "commit"), "0123456789abc"),
                       "is not in this repository"),
    "no-link": (lambda m: "\n".join(
        " | ".join(c if i != 3 else "see the records" for i, c in enumerate(l.split(" | ")))
        if l.startswith("| E3 |") else l for l in m.split("\n")), "no evidence link"),
    "missing-row": (lambda m: "\n".join(l for l in m.split("\n") if not l.startswith("| E5 |")), "rows"),
    "changed-criterion": (lambda m: _replace_in_row(m, "E1", "same WER", "similar WER"), "the overview says"),
}


@pytest.mark.parametrize("brk", list(EVIDENCE_BREAKS), ids=list(EVIDENCE_BREAKS))
def test_FR_0_9_01_evidence_check_reports_each_broken_link(memo, tests, brk):
    edit, expected = EVIDENCE_BREAKS[brk]
    edited = edit(memo)
    assert edited != memo
    problems = exit_criteria_problems(edited, tests)
    assert any(expected in p for p in problems), problems


def test_FR_0_9_01_decisions_quote_their_approval_files(memo):
    assert quote_problems(memo) == []
    quote = re.search(r'\| "([^"]{20,})" \|', memo).group(1)
    assert quote_problems(memo.replace(quote, quote[:-3] + "xyz", 1)) != []


def test_FR_0_9_01_open_issues_list_every_open_debt_and_blocker(memo):
    assert open_issue_problems(memo) == []
    body = sections(memo)["Open issues"]
    assert open_issue_problems(memo.replace(body, body.replace("DEBT-025", "DEBT-0XX"))) != []


def test_FR_0_9_01_audit_round_counts_and_lessons_cite_records(memo):
    assert lesson_problems(memo) == []
    body = sections(memo)["Lessons for the process"]
    assert lesson_problems(memo.replace(body, body.replace("| WP-0.0 | 9 |", "| WP-0.0 | 8 |"))) != []


def test_FR_0_9_01_no_open_debt_row_targets_phase_0():
    # Must-catch 2: closed, or moved to a named later WP with the owner's approval.
    assert debt_problems(read(DEBT)) == []


DEBT_BREAKS = {
    "left-open": (lambda t: _status(t, "DEBT-001", "OPEN"), "DEBT-001: targets WP-0.9 (phase 0) but is OPEN"),
    "moved-without-approval": (lambda t: t.replace("`docs/approvals/WP-0.9.md`, question 8", "`docs/approvals/WP-0.8.md`")
                               .replace("(`docs/approvals/WP-0.9.md` on `main` (`699acd5`), question 8:",
                                        "(`docs/approvals/WP-0.8.md`, question 8:"),
                               "DEBT-025: no cited approval names"),
    "moved-to-unnamed-wp": (lambda t: t.replace("| WP-4.5 (moved from WP-0.9", "| a later phase (moved from WP-0.9"),
                            "DEBT-025: moved, but the Target cell does not start with a WP ID"),
}


def _status(text, debt, status):
    lines = text.split("\n")
    i = next(i for i, l in enumerate(lines) if l.startswith(f"| {debt} |"))
    cells = lines[i].split(" | ")
    cells[6] = status + " |"
    lines[i] = " | ".join(cells)
    return "\n".join(lines)


@pytest.mark.parametrize("brk", list(DEBT_BREAKS), ids=list(DEBT_BREAKS))
def test_FR_0_9_01_debt_check_reports_open_or_unapproved_rows(brk):
    edit, expected = DEBT_BREAKS[brk]
    text = read(DEBT)
    edited = edit(text)
    assert edited != text
    problems = debt_problems(edited)
    assert any(expected in p for p in problems), problems


def test_FR_0_9_01_memo_passes_every_check(memo, tests):
    assert memo_problems(memo, tests) == []


def test_FR_0_9_02_unit_log_copy_is_consistent():
    # Each row's hours and estimate recomputed from start, end and the rate table.
    assert unit_log_problems() == []


def test_FR_0_9_02_phase_1_prerequisites_come_from_their_sources(memo):
    assert prerequisite_problems(memo) == []
    subs = sections(sections(memo)["Phase 1 prerequisites"], 3)
    units = subs["Colab compute units used so far"]
    assert prerequisite_problems(memo.replace(units, units.replace("| Total | 2 |", "| Total | 3 |"))) != []
    plan = subs["Pack v1 plan"]
    assert prerequisite_problems(memo.replace(plan, plan + "\n- The pack has 3,000 clips.\n")) != []


def test_FR_0_9_03_memo_links_phase_audit_report_and_its_verdict(memo):
    assert phase_audit_problems(memo) == []


def test_FR_0_9_03_phase_audit_check_follows_the_approved_order(tmp_path, memo):
    # A report that exists must be stated; a missing one is allowed only while WP-0.9 is before READY-FOR-AUDIT and the
    # memo says the audit is pending. Checked on a copy of the records the check reads.
    from aqis_testutil import ROOT
    for rel in ("docs/progress/STATUS.md", MEMO, PHASE_AUDIT):
        if (ROOT / rel).exists():
            (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, tmp_path / rel)
    (tmp_path / PHASE_AUDIT).unlink(missing_ok=True)
    status_file = tmp_path / "docs/progress/STATUS.md"
    status = status_file.read_text(encoding="utf-8")
    in_build = re.sub(r"^(\| WP-0\.9 \| [^|]+\| )[A-Z-]+( \|)", r"\1IN-BUILD\2", status, flags=re.M)
    ready = re.sub(r"^(\| WP-0\.9 \| [^|]+\| )[A-Z-]+( \|)", r"\1READY-FOR-AUDIT\2", status, flags=re.M)
    body = sections(memo)["Phase audit"]
    pending = memo.replace(body, f"\nReport: `{PHASE_AUDIT}`\n\n{PENDING_LINE}\n\n")
    claimed = memo.replace(body, f"\nReport: `{PHASE_AUDIT}`\n\nVerdict: PASS\n\n")
    status_file.write_text(in_build, encoding="utf-8")
    assert phase_audit_problems(pending, tmp_path) == []
    assert phase_audit_problems(claimed, tmp_path) != []          # a verdict without a report
    status_file.write_text(ready, encoding="utf-8")
    assert phase_audit_problems(pending, tmp_path) != []          # ready for audit without the report
    (tmp_path / PHASE_AUDIT).write_text("# Phase 0 audit\n\nCommit audited: `0123456`\n\n## Verdict: PASS\n",
                                        encoding="utf-8")
    assert any("still says the audit is pending" in p for p in phase_audit_problems(pending, tmp_path))
