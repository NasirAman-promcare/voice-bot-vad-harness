"""WP-0.9: the Phase 0 memo (docs/progress/PHASE0_MEMO.md) and the phase 0 debt rows.

FR-0.9-01: exit criteria E1 to E6 with evidence that exists (must-catch 1), decisions quoted from the approvals,
open issues and lessons tied to records; every phase 0 debt row closed or moved with approval (must-catch 2).
FR-0.9-02: the phase 1 prerequisites from their sources. FR-0.9-03: the memo links the phase audit report.
"""
import os
import re
import shutil
import subprocess

import pytest

from aqis_testutil import ROOT
from aqis_memo_testutil import (DEBT, MEMO, PENDING_LINE, PHASE0_DEBT_IDS, PHASE_AUDIT, RATES, REVIEWED_WPS,
                                SECTIONS, UNIT_LOG, WP09_START, audit_rounds, collected_test_names, debt_problems,
                                debt_rows, exit_criteria_problems, lesson_problems, memo_problems,
                                open_issue_problems, phase_audit_problems, prerequisite_problems, quote_problems,
                                read, sections, unit_log_problems)


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
    # WP-0.9-F07: a folder, or a path outside the repository, is not evidence that exists.
    "folder-link": (lambda m: _replace_in_row(m, "E4", _first_span(m, "E4", "path"), "docs/baselines/tier2_vad/2026-10-03"),
                    "is not a file in this repository"),
    "outside-repository": (lambda m: _replace_in_row(m, "E4", _first_span(m, "E4", "path"), "/etc/hostname"),
                           "is not a file in this repository"),
    "escaping-repository": (lambda m: _replace_in_row(m, "E4", _first_span(m, "E4", "path"), "docs/" + "../" * len(ROOT.resolve().parts) + "etc/hostname"),
                            "is not a file in this repository"),
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


def test_FR_0_9_01_audit_rounds_cover_only_the_reviewed_wps():
    # WP-0.9-F02: WP-0.9's own AUDIT.md (written by /wp-audit WP-0.9, every round) is not part of the memo's review.
    assert (ROOT / "docs/progress/WP-0.9/AUDIT.md").is_file()
    assert sorted(audit_rounds()) == list(REVIEWED_WPS) == [f"WP-0.{n}" for n in range(9)]


def test_FR_0_9_01_no_open_debt_row_targets_phase_0():
    # Must-catch 2: closed, or moved to a named later WP with the owner's approval.
    assert debt_problems(read(DEBT)) == []


NEW_DEBT_ID = f"DEBT-{max(int(row[0].split('-')[1]) for row in debt_rows(read(DEBT))) + 1:03d}"
DEBT_BREAKS = {
    "left-open": (lambda t: _status(t, "DEBT-001", "OPEN"), "DEBT-001: targets WP-0.9 (phase 0) but is OPEN"),
    "moved-without-approval": (lambda t: t.replace("`docs/approvals/WP-0.9.md`, question 8", "`docs/approvals/WP-0.8.md`")
                               .replace("(`docs/approvals/WP-0.9.md` on `main` (`699acd5`), question 8:",
                                        "(`docs/approvals/WP-0.8.md`, question 8:"),
                               "DEBT-025: no cited approval names"),
    "moved-to-unnamed-wp": (lambda t: t.replace("| WP-4.5 (moved from WP-0.9", "| a later phase (moved from WP-0.9"),
                            "DEBT-025: moved, but the Target cell does not start with a WP ID"),
    # WP-0.9-F08 (auditor break A15-1): WP-0.9.md names DEBT-016 (question 5, closed) and WP-4.5 (question 8, for
    # DEBT-025), but on different lines, so it does not approve moving DEBT-016 to WP-4.5.
    "moved-citing-unrelated-lines": (lambda t: _target_and_status(t, "DEBT-016", "WP-4.5",
                                                                  "OPEN (`docs/approvals/WP-0.9.md`, question 5)"),
                                     "DEBT-016: no cited approval names DEBT-016 (or WP-0.6-F06) and WP-4.5 on one line"),
    # WP-0.9-F11 (auditor break A15-4): a new row, not pinned, left OPEN at a phase 0 target is reported too. The
    # row takes the next unused ID, so a real row added later never collides with it (BLK-018).
    "new-unpinned-row-open-at-phase-0": (lambda t: _new_row(t, "DEBT-033", NEW_DEBT_ID, "WP-0.9", "OPEN"),
                                         f"{NEW_DEBT_ID}: targets WP-0.9 (phase 0) but is OPEN"),
}


def _new_row(text, model, debt, target, status):
    lines = text.split("\n")
    i = next(i for i, l in enumerate(lines) if l.startswith(f"| {model} |"))
    cells = lines[i].split(" | ")
    cells[0], cells[5], cells[6] = f"| {debt}", target, status + " |"
    lines.insert(i + 1, " | ".join(cells))
    return "\n".join(lines)


def _status(text, debt, status):
    lines = text.split("\n")
    i = next(i for i, l in enumerate(lines) if l.startswith(f"| {debt} |"))
    cells = lines[i].split(" | ")
    cells[6] = status + " |"
    lines[i] = " | ".join(cells)
    return "\n".join(lines)


def _target_and_status(text, debt, target, status):
    lines = text.split("\n")
    i = next(i for i, l in enumerate(lines) if l.startswith(f"| {debt} |"))
    cells = lines[i].split(" | ")
    cells[5], cells[6] = target, status + " |"
    lines[i] = " | ".join(cells)
    return "\n".join(lines)


def test_FR_0_9_01_pinned_phase0_debt_ids_are_the_phase0_rows_before_wp09():
    # WP-0.9-F01: the rows must-catch 2 covers are pinned, independently of how each row is worded now. The pin is
    # checked against DEBT.md at 254c1e3, the commit WP-0.9 started from.
    before = subprocess.run(["git", "show", f"{WP09_START}:{DEBT}"], cwd=ROOT, capture_output=True, text=True,
                            check=True).stdout
    phase0 = [row[0] for row in debt_rows(before) if re.match(r"WP-0\.\d+\b", row[5])]
    assert list(PHASE0_DEBT_IDS) == phase0 and len(phase0) == 30


@pytest.mark.parametrize("debt", PHASE0_DEBT_IDS)
def test_FR_0_9_01_debt_check_covers_every_pinned_row(debt):
    # WP-0.9-F01 (auditor breaks MC2-a, MC2-f to MC2-h): each pinned row, left OPEN at a phase 0 target, rewritten to a
    # later WP without the word "moved" and without an approval, or deleted, is reported, whatever its current state.
    text = read(DEBT)
    reopened = _target_and_status(text, debt, "WP-0.9", "OPEN")
    assert any(p.startswith(f"{debt}: targets WP-0.9 (phase 0) but is OPEN") for p in debt_problems(reopened))
    quiet_move = _target_and_status(text, debt, "WP-1.0", "OPEN")
    assert any(p.startswith(f"{debt}: no cited approval names {debt}") for p in debt_problems(quiet_move)), debt
    deleted = "\n".join(l for l in text.split("\n") if not l.startswith(f"| {debt} |"))
    assert any(p.startswith(f"{debt}: missing") for p in debt_problems(deleted))


@pytest.mark.parametrize("brk", list(DEBT_BREAKS), ids=list(DEBT_BREAKS))
def test_FR_0_9_01_debt_check_reports_open_or_unapproved_rows(brk):
    edit, expected = DEBT_BREAKS[brk]
    text = read(DEBT)
    edited = edit(text)
    assert edited != text
    problems = debt_problems(edited)
    assert any(expected in p for p in problems), problems


@pytest.mark.parametrize("line, approved", [
    ("- {debt} moves to {wp}.", True),
    ("- {finding} (the row's finding) moves to {wp}.", True),
    ("- {debt} is closed.\n- DEBT-099 moves to {wp}.", False),
    ("- {finding}0 moves to {wp}.", False),
    ("- {debt}0 moves to {wp}.", False),
    ("- {debt} moves to {wp}0.", False),
    ("- X{debt} moves to {wp}.", False),
], ids=["debt-and-wp", "finding-and-wp", "different-lines", "longer-finding-id", "longer-debt-id", "longer-wp-id",
        "longer-debt-id-on-the-left"])
def test_FR_0_9_01_move_approval_names_row_and_wp_on_one_line(tmp_path, line, approved):
    # WP-0.9-F08: an approval allows a move only on a line that names the row (its debt ID or its finding ID) and the
    # new WP, each as a whole ID. Checked against a copy of the approvals folder holding only this approval line.
    debt, wp = "DEBT-016", "WP-4.5"
    finding = next(row[1] for row in debt_rows(read(DEBT)) if row[0] == debt).split()[0]
    approval = tmp_path / "docs/approvals/WP-9.9.md"
    approval.parent.mkdir(parents=True)
    approval.write_text("STATUS: APPROVED\n" + line.format(debt=debt, finding=finding, wp=wp) + "\n", encoding="utf-8")
    moved = _target_and_status(read(DEBT), debt, wp, "OPEN (`docs/approvals/WP-9.9.md`)")
    problems = [p for p in debt_problems(moved, tmp_path) if p.startswith(f"{debt}:")]
    assert problems == ([] if approved else
                        [f"{debt}: no cited approval names {debt} (or {finding}) and {wp} on one line"])


def test_FR_0_9_01_memo_passes_every_check(memo, tests):
    assert memo_problems(memo, tests) == []


def test_FR_0_9_02_unit_log_copy_is_consistent():
    # Each row's hours and estimate recomputed from start, end and the rate table.
    assert unit_log_problems() == []


@pytest.mark.parametrize("column, old, new", [("estimated_units", "0.0432", "0.0433"), ("hours", "0.0363", "0.0364"),
                                              ("units_per_hour", ",1.19,", ",1.20,")])
def test_FR_0_9_02_unit_log_check_reports_a_wrong_row(tmp_path, column, old, new):
    # WP-0.9-F03 (auditor break X8): a row whose hours, rate or estimate does not follow from its start, end and the
    # rate table is reported. Checked on a copy of the unit log and the rate table.
    for rel in (UNIT_LOG, RATES):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, tmp_path / rel)
    assert unit_log_problems(tmp_path) == []
    log = tmp_path / UNIT_LOG
    text = log.read_text(encoding="utf-8")
    assert text.count(old) == 1, column
    log.write_text(text.replace(old, new), encoding="utf-8")
    problems = unit_log_problems(tmp_path)
    assert len(problems) == 1 and problems[0].startswith("colab-2026-10-02-1e6bd941ec9e: "), problems


@pytest.mark.parametrize("old, new", [("0 of 22 recruited", "12 of 22 recruited"),
                                      ("planned use 40 of them", "planned use 45 of them"),
                                      ("OC-0.8-03 bootstrap are noted as unmetered", "OC-0.8-03 bootstrap are metered")])
def test_FR_0_9_02_owner_quotes_must_be_in_the_approval(memo, old, new):
    # WP-0.9-F03 (auditor break X9): the owner's recruiting status, budget and unmetered sessions are quoted from the
    # approval; a changed figure is reported.
    assert memo.count(old) == 1
    problems = prerequisite_problems(memo.replace(old, new))
    assert any("is not in docs/approvals/WP-0.9.md" in p for p in problems), problems


BAD_PATHS = {
    "folder": "docs/recording",
    "outside-repository": "/etc/hostname",
    "escaping-repository": "docs/" + "../" * len(ROOT.resolve().parts) + "etc/hostname",
}


@pytest.mark.parametrize("kind", list(BAD_PATHS), ids=list(BAD_PATHS))
def test_FR_0_9_01_lessons_cite_files_in_the_repository(memo, kind):
    # WP-0.9-F10 (auditor break A15-2): a lesson's record must be a file in this repository, as for evidence links.
    bad = BAD_PATHS[kind]
    assert os.path.exists(bad) or os.path.exists(ROOT / bad)
    body = sections(memo)["Lessons for the process"]
    edited = memo.replace(body, body.replace("`docs/process/AUDIT_PROTOCOL.md`", f"`{bad}`", 1))
    assert edited != memo
    assert any(p.endswith(f"cites {bad}, which does not exist") for p in lesson_problems(edited)), bad


@pytest.mark.parametrize("kind", list(BAD_PATHS), ids=list(BAD_PATHS))
def test_FR_0_9_02_pack_v1_plan_cites_files_in_the_repository(memo, kind):
    # WP-0.9-F10 (auditor break A15-3): a Pack v1 plan bullet's path must be a file in this repository.
    bad = BAD_PATHS[kind]
    assert os.path.exists(bad) or os.path.exists(ROOT / bad)
    plan = sections(sections(memo)["Phase 1 prerequisites"], 3)["Pack v1 plan"]
    edited = memo.replace(plan, plan.replace("`docs/recording/RECORDING_GUIDE.md`", f"`{bad}`", 1))
    assert edited != memo
    assert f"Pack v1 plan cites {bad}, which does not exist" in prerequisite_problems(edited), bad


def test_FR_0_9_02_phase_1_prerequisites_come_from_their_sources(memo):
    assert prerequisite_problems(memo) == []
    subs = sections(sections(memo)["Phase 1 prerequisites"], 3)
    units = subs["Colab compute units used so far"]
    assert prerequisite_problems(memo.replace(units, units.replace("| Total | 2 |", "| Total | 3 |"))) != []
    plan = subs["Pack v1 plan"]
    assert prerequisite_problems(memo.replace(plan, plan + "\n- The pack has 3,000 clips.\n")) != []


def test_FR_0_9_03_memo_links_phase_audit_report_and_its_verdict(memo):
    assert phase_audit_problems(memo) == []


def test_FR_0_9_03_memo_verdict_and_commit_must_be_the_reports(memo):
    # WP-0.9-F03 (auditor break X1): the memo must state the report's verdict and audited commit.
    assert re.search(r"^Verdict: PASS$", memo, re.M)
    assert phase_audit_problems(memo.replace("\nVerdict: PASS\n", "\nVerdict: FAIL\n")) == [
        "Phase audit does not state the report's verdict PASS"]
    line = re.search(r"^Commit audited: `([0-9a-f]+)`$", memo, re.M).group(0)
    assert phase_audit_problems(memo.replace(line, "Commit audited: `8365189746a315e27f02ecbfd19d7f9d18d3b80a`")) == [
        "Phase audit does not state the report's audited commit 079571e14752"]


def test_FR_0_9_03_audited_commit_must_be_an_ancestor_of_head(tmp_path, memo):
    # WP-0.9-F03 (auditor break X2): a report of a commit that is not in this branch's history is reported. Checked in
    # a clone of this repository without a work tree, where a commit outside HEAD's history is made with commit-tree.
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(ROOT), str(clone)], check=True)
    tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=clone, capture_output=True, text=True,
                          check=True).stdout.strip()
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
    side = subprocess.run(["git", "commit-tree", tree, "-m", "a commit outside HEAD's history"], cwd=clone,
                          capture_output=True, text=True, check=True, env=env).stdout.strip()
    report = (ROOT / PHASE_AUDIT).read_text(encoding="utf-8")
    audited = re.search(r"Commit audited: `([0-9a-f]{40})`", report).group(1)
    (clone / PHASE_AUDIT).parent.mkdir(parents=True, exist_ok=True)
    (clone / PHASE_AUDIT).write_text(report, encoding="utf-8")
    assert phase_audit_problems(memo, clone) == []                      # the real report: its commit is an ancestor
    (clone / PHASE_AUDIT).write_text(report.replace(audited, side), encoding="utf-8")
    moved = memo.replace(f"Commit audited: `{audited}`", f"Commit audited: `{side}`")
    assert phase_audit_problems(moved, clone) == [f"the audited commit {side[:12]} is not an ancestor of HEAD"]


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
