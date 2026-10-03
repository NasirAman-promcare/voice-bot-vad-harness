"""Checks for the Phase 0 memo (docs/progress/PHASE0_MEMO.md, WP-0.9) and the debt register's phase 0 rows.

Every check returns a list of problem strings (empty means it passed), so the self-tests can run it on edited
copies. Expected values are read from the repository (the overview, approvals, DEBT.md, AUDIT.md files, the unit
log and the rate table), never from the memo itself.
"""
import csv
import io
import re
import subprocess
import sys
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction
from pathlib import Path

import yaml

from aqis_testutil import ROOT

MEMO = "docs/progress/PHASE0_MEMO.md"
OVERVIEW = "docs/specs/phase-0/00-PHASE-0-OVERVIEW.md"
DEBT = "docs/progress/DEBT.md"
BLOCKERS = "docs/progress/BLOCKERS.md"
UNIT_LOG = "docs/progress/WP-0.9/OC-0.9-01_units.csv"
RATES = "config/aqis_lab/colab_rates.yaml"
BUILD_PLAN = "docs/specs/sources/AQIS_Test_Lab_Build_Plan.md"
PHASE_AUDIT = "docs/progress/PHASE-0-AUDIT.md"
REPO_URL = "https://github.com/NasirAman-promcare/voice-bot-vad-harness"
SECTIONS = ["Scope", "Exit criteria", "Decisions taken", "Open issues", "Lessons for the process",
            "Phase 1 prerequisites", "Phase audit"]
PREREQUISITES = ["Campaign A recruiting status", "Pack v1 plan", "Colab compute units used so far"]
STATUSES = ("MET", "MET with note", "NOT MET")
UNIT_LOG_HEADER = ["session_id", "platform", "gpu_type", "start_utc", "end_utc", "end_basis", "hours", "runtime",
                   "units_per_hour", "estimated_units", "rate_source"]
OWNER_BLANK_RE = re.compile(r"\[OWNER DECIDES: [^\]]+\]")
CODE_RE = re.compile(r"`([^`]+)`")
LINK_RE = re.compile(r"\]\((https?://[^)\s]+)\)")
SHA_RE = re.compile(r"[0-9a-f]{7,40}")
BUILD_PLAN_CITE_RE = re.compile(r"\[Build Plan § ([^\]]+)\]")


def read(rel, root=ROOT):
    return (Path(root) / rel).read_text(encoding="utf-8")


def sections(text, level=2):
    """{heading: body} for headings of exactly this level."""
    found, current, lines = {}, None, []
    marker = "#" * level + " "
    for line in text.splitlines():
        if line.startswith(marker) and not line.startswith(marker + "#"):
            if current is not None:
                found[current] = "\n".join(lines)
            current, lines = line[len(marker):].strip(), []
        elif current is not None:
            if re.match(r"^#{1,%d} " % (level - 1), line):
                found[current] = "\n".join(lines)
                current, lines = None, []
            else:
                lines.append(line)
    if current is not None:
        found[current] = "\n".join(lines)
    return found


def table(body, first_header):
    """(header, [row dicts]) of the pipe table in body whose first header cell is first_header."""
    lines = body.splitlines()
    for i, line in enumerate(lines):
        cells = _cells(line)
        if line.startswith("|") and cells and cells[0] == first_header:
            rows = []
            for row in lines[i + 2:]:
                if not row.startswith("|"):
                    break
                values = _cells(row)
                if len(values) != len(cells):
                    raise ValueError(f"row {row!r} has {len(values)} cells, the header {len(cells)}")
                rows.append(dict(zip(cells, values)))
            return cells, rows
    raise ValueError(f"no table headed {first_header!r}")


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def flat(text):
    return " ".join(text.replace("**", "").split())


def overview_criteria(root=ROOT):
    """{ID: 'Name: text'} for E1 to E6 as the phase 0 overview states them."""
    found = {}
    for m in re.finditer(r"^- \*\*(E\d) ([^*]+)\*\*: (.+)$", read(OVERVIEW, root), re.M):
        found[m.group(1)] = f"{m.group(2).strip()}: {m.group(3).strip()}"
    return found


def collected_test_names(root=ROOT):
    """Names of the tests pytest collects under tests/aqis_lab (parameters dropped)."""
    proc = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
                           "tests/aqis_lab"], cwd=root, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout[-2000:] + proc.stderr[-2000:])
    return {line.rsplit("::", 1)[1].split("[", 1)[0] for line in proc.stdout.splitlines() if "::" in line}


def _commit_exists(sha, root):
    return subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=root, capture_output=True).returncode == 0


def link_problems(cell, root, tests, where):
    """Problems with the evidence links of one cell: every code span is an existing repository path, a collected test
    name or a commit of this repository; every URL is a run or pull request of this repository; at least one link
    is a path or a test (a URL alone is not evidence that is kept in the repository)."""
    problems, kept = [], 0
    for span in CODE_RE.findall(cell):
        if span.startswith("test_"):
            if span not in tests:
                problems.append(f"{where}: test {span} is not collected by pytest")
            kept += 1
        elif SHA_RE.fullmatch(span):
            if not _commit_exists(span, root):
                problems.append(f"{where}: commit {span} is not in this repository")
        elif "/" in span or "." in span:
            if not (Path(root) / span).exists():
                problems.append(f"{where}: path {span} does not exist")
            kept += 1
        else:
            problems.append(f"{where}: `{span}` is not a path, a test name or a commit")
    for url in LINK_RE.findall(cell):
        if not re.fullmatch(re.escape(REPO_URL) + r"/(actions/runs/\d+|pull/\d+)", url):
            problems.append(f"{where}: {url} is not a run or pull request of this repository")
    if not kept:
        problems.append(f"{where}: no evidence link to a repository path or a test")
    return problems


def exit_criteria_problems(text, tests, root=ROOT):
    """Must-catch 1: each exit criterion E1 to E6 appears once, in order, with the overview's words, a status, and
    evidence links that all exist."""
    try:
        header, rows = table(sections(text).get("Exit criteria", ""), "ID")
    except ValueError as exc:
        return [f"Exit criteria: {exc}"]
    expected = overview_criteria(root)
    problems = []
    if header != ["ID", "Criterion", "Status", "Evidence", "Note"]:
        problems.append(f"Exit criteria columns {header}")
    ids = [r["ID"] for r in rows]
    if ids != sorted(expected):
        problems.append(f"Exit criteria rows {ids}, expected {sorted(expected)}")
    for r in rows:
        if r["ID"] not in expected:
            continue
        if flat(r.get("Criterion", "")) != expected[r["ID"]]:
            problems.append(f"{r['ID']}: criterion {flat(r.get('Criterion', ''))!r}, the overview says "
                            f"{expected[r['ID']]!r}")
        if r.get("Status") not in STATUSES:
            problems.append(f"{r['ID']}: status {r.get('Status')!r}, expected one of {STATUSES}")
        if r.get("Status") != "MET" and r.get("Note", "").strip() in ("", "—"):
            problems.append(f"{r['ID']}: MET with note has no note")
        problems += link_problems(r.get("Evidence", ""), root, tests, r["ID"])
    return problems


def quote_problems(text, root=ROOT):
    """Each Decisions row quotes its approval file on main word for word (whitespace aside)."""
    try:
        _, rows = table(sections(text).get("Decisions taken", ""), "Decision")
    except ValueError as exc:
        return [f"Decisions taken: {exc}"]
    problems = []
    if len(rows) < 8:
        problems.append(f"Decisions taken has {len(rows)} rows")
    for r in rows:
        paths = CODE_RE.findall(r.get("Approval", ""))
        quote = re.fullmatch(r'"(.+)"', r.get("Quote", "").strip())
        if len(paths) != 1 or not re.fullmatch(r"docs/approvals/WP-\d+\.\d+\.md", paths[0]):
            problems.append(f"{r['Decision']}: approval cell {r.get('Approval')!r} is not one approval file")
            continue
        if not quote:
            problems.append(f"{r['Decision']}: quote cell is not one quoted passage")
            continue
        source = (Path(root) / paths[0])
        if not source.is_file() or " ".join(quote.group(1).split()) not in " ".join(source.read_text("utf-8").split()):
            problems.append(f"{r['Decision']}: the quote is not in {paths[0]}")
    return problems


def open_debt_ids(debt_text):
    return [row[0] for row in debt_rows(debt_text) if row[6].startswith("OPEN")]


def debt_rows(debt_text):
    return [[c.strip() for c in line.strip().strip("|").split(" | ")] for line in debt_text.splitlines()
            if line.startswith("| DEBT-")]


def open_issue_problems(text, root=ROOT):
    """Open issues names every OPEN debt row and every OPEN blocker, and no CLOSED debt row as open."""
    body = sections(text).get("Open issues", "")
    problems = []
    rows = debt_rows(read(DEBT, root))
    for row in rows:
        named = re.search(rf"\b{row[0]}\b", body)
        if row[6].startswith("OPEN") and not named:
            problems.append(f"Open issues does not name {row[0]}, which is OPEN in {DEBT}")
    closed = {row[0] for row in rows if row[6].startswith("CLOSED")}
    for line in body.splitlines():
        if line.startswith("- ") and "permanent limit" not in line:
            for debt in re.findall(r"\bDEBT-\d{3}\b", line):
                if debt in closed:
                    problems.append(f"Open issues lists {debt}, which is CLOSED in {DEBT}")
    for m in re.finditer(r"^## (BLK-\d+)[^\n]*\nSTATUS: OPEN", read(BLOCKERS, root), re.M):
        if m.group(1) not in body:
            problems.append(f"Open issues does not name {m.group(1)}, which is OPEN in {BLOCKERS}")
    return problems


def audit_rounds(root=ROOT):
    """{WP: final audit round} read from each WP's AUDIT.md header."""
    rounds = {}
    for path in sorted((Path(root) / "docs" / "progress").glob("WP-0.*/AUDIT.md")):
        head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:3])
        m = re.search(r"round (\d+)", head, re.I)
        if m:
            rounds[path.parent.name] = int(m.group(1))
    return rounds


def lesson_problems(text, root=ROOT):
    """Each lesson cites at least one committed record, and the audit-round table equals the AUDIT.md files."""
    body = sections(text).get("Lessons for the process", "")
    problems = []
    lessons = [l for l in body.splitlines() if re.match(r"^\d+\. ", l)]
    if len(lessons) < 5:
        problems.append(f"Lessons has {len(lessons)} numbered lessons")
    for lesson in lessons:
        paths = [s for s in CODE_RE.findall(lesson) if "/" in s]
        if not paths:
            problems.append(f"lesson {lesson[:40]!r} cites no record")
        for p in paths:
            if not (Path(root) / p).exists():
                problems.append(f"lesson {lesson[:40]!r} cites {p}, which does not exist")
    try:
        _, rows = table(body, "WP")
    except ValueError as exc:
        return problems + [f"Lessons: {exc}"]
    shown = {r["WP"]: int(r["Audit rounds"]) for r in rows}
    if shown != audit_rounds(root):
        problems.append(f"audit rounds {shown}, the AUDIT.md files say {audit_rounds(root)}")
    return problems


def debt_problems(debt_text, root=ROOT):
    """Must-catch 2: every DEBT row targeting phase 0 is CLOSED; a row moved to a later WP names that WP first in its
    Target cell and cites an approval on main that names both the row (or its finding) and that WP."""
    problems = []
    for row in debt_rows(debt_text):
        debt, finding, target, status = row[0], row[1], row[5], row[6]
        if re.match(r"WP-0\.\d+\b", target) and not status.startswith("CLOSED"):
            problems.append(f"{debt}: targets {target.split()[0]} (phase 0) but is {status.split()[0]}")
        for cited in set(re.findall(r"docs/approvals/[\w.-]+\.md", status)):
            if not (Path(root) / cited).is_file():
                problems.append(f"{debt}: cites {cited}, which does not exist")
        if "moved" in target.lower() or status.startswith("OPEN, moved"):
            new = re.match(r"(WP-\d+\.\d+)\b", target)
            approvals = set(re.findall(r"docs/approvals/[\w.-]+\.md", target + " " + status))
            if not new:
                problems.append(f"{debt}: moved, but the Target cell does not start with a WP ID")
                continue
            texts = [(Path(root) / a).read_text("utf-8") for a in approvals if (Path(root) / a).is_file()]
            finding_id = finding.split()[0]
            if not any((debt in t or finding_id in t) and new.group(1) in t for t in texts):
                problems.append(f"{debt}: no cited approval names {debt} (or {finding_id}) and {new.group(1)}")
    return problems


def unit_rows(root=ROOT):
    text = read(UNIT_LOG, root)
    reader = csv.reader(io.StringIO(text))
    header = next(reader)
    return header, [dict(zip(header, r)) for r in reader if r]


def _hours(start, end):
    fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
    delta = datetime.strptime(end, fmt) - datetime.strptime(start, fmt)
    micro = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
    return Fraction(micro, 3_600_000_000)


def _round4(value):
    """A Fraction rounded half-even to 4 decimal places, exactly (the unit log's rule)."""
    scaled = value * 10_000
    whole, rest = divmod(scaled.numerator, scaled.denominator)
    if 2 * rest > scaled.denominator or (2 * rest == scaled.denominator and whole % 2):
        whole += 1
    return Decimal(whole).scaleb(-4)


def unit_log_problems(root=ROOT):
    """The committed unit-log copy has the unit log's header, and every row's hours and estimate follow from its start,
    end and the rate table (recomputed exactly here, rounded half-even to 4 places)."""
    header, rows = unit_rows(root)
    problems = [] if header == UNIT_LOG_HEADER else [f"unit log header {header}"]
    rates = {r["runtime"]: r["units_per_hour"] for r in yaml.safe_load(read(RATES, root))["rates"]}
    if not rows:
        problems.append("the unit log has no rows")
    for r in rows:
        hours = _hours(r["start_utc"], r["end_utc"])
        if str(_round4(hours)) != r["hours"]:
            problems.append(f"{r['session_id']}: hours {r['hours']}, start to end gives {_round4(hours)}")
        if rates.get(r["runtime"]) != r["units_per_hour"]:
            problems.append(f"{r['session_id']}: rate {r['units_per_hour']}, the rate table says {rates.get(r['runtime'])}")
            continue
        exact = hours * Fraction(Decimal(rates[r["runtime"]]))
        if str(_round4(exact)) != r["estimated_units"]:
            problems.append(f"{r['session_id']}: estimate {r['estimated_units']}, recomputed {_round4(exact)}")
    return problems


def unit_totals(root=ROOT):
    """{runtime: (sessions, hours, units)} plus 'Total', summing the logged values exactly."""
    _, rows = unit_rows(root)
    totals = {}
    for r in rows:
        s, h, u = totals.get(r["runtime"], (0, Decimal(0), Decimal(0)))
        totals[r["runtime"]] = (s + 1, h + Decimal(r["hours"]), u + Decimal(r["estimated_units"]))
    totals["Total"] = (len(rows), sum((Decimal(r["hours"]) for r in rows), Decimal(0)),
                       sum((Decimal(r["estimated_units"]) for r in rows), Decimal(0)))
    return totals


def prerequisite_problems(text, root=ROOT):
    """FR-0.9-02: the three phase 1 prerequisites, each from its source."""
    body = sections(text).get("Phase 1 prerequisites", "")
    subs = sections(body, 3)
    problems = []
    if list(subs) != PREREQUISITES:
        return [f"Phase 1 prerequisites subsections {list(subs)}, expected {PREREQUISITES}"]
    # The owner's facts (recruiting status, budget, unmetered sessions) are quoted from the approval, never restated.
    approval = " ".join(read("docs/approvals/WP-0.9.md", root).split())
    for name in ("Campaign A recruiting status", "Colab compute units used so far"):
        quotes = re.findall(r'^> "(.+)"$', subs[name], re.M)
        if not quotes:
            problems.append(f"{name}: no quoted owner statement")
        for quote in quotes:
            if " ".join(quote.split()) not in approval:
                problems.append(f"{name}: the quote {quote[:50]!r} is not in docs/approvals/WP-0.9.md")
    # Pack v1 plan: every bullet cites a Build Plan section, a committed file, or is an owner decision.
    headings = {l.lstrip("#").strip() for l in read(BUILD_PLAN, root).splitlines() if l.startswith("#")}
    plan_text = " ".join(read(BUILD_PLAN, root).split())
    bullets = [l for l in subs["Pack v1 plan"].splitlines() if l.startswith("- ")]
    blanks = 0
    for b in bullets:
        cites = BUILD_PLAN_CITE_RE.findall(b)
        paths = [s for s in CODE_RE.findall(b) if "/" in s]
        blank = OWNER_BLANK_RE.search(b)
        blanks += bool(blank)
        if not (cites or paths or blank):
            problems.append(f"Pack v1 plan bullet {b[:50]!r} cites no source and is not an owner decision")
        for c in cites:
            if c not in headings:
                problems.append(f"Pack v1 plan cites Build Plan § {c}, which is not a heading of the Build Plan")
        for p in paths:
            if not (Path(root) / p).exists():
                problems.append(f"Pack v1 plan cites {p}, which does not exist")
        for quote in (re.findall(r'"([^"]+)"', b) if cites else []):
            if " ".join(quote.split()) not in plan_text:
                problems.append(f"Pack v1 plan quotes {quote!r}, which the Build Plan does not say")
    if blanks < 3:
        problems.append(f"Pack v1 plan has {blanks} owner decisions marked")
    # Compute units: the table equals the unit log's totals.
    try:
        _, rows = table(subs["Colab compute units used so far"], "Runtime")
    except ValueError as exc:
        return problems + [f"Colab compute units: {exc}"]
    shown = {r["Runtime"]: (int(r["Sessions"]), Decimal(r["Hours"]), Decimal(r["Estimated units"])) for r in rows}
    if shown != unit_totals(root):
        problems.append(f"compute units {shown}, the unit log gives {unit_totals(root)}")
    if UNIT_LOG not in subs["Colab compute units used so far"]:
        problems.append(f"Colab compute units does not name {UNIT_LOG}")
    return problems


def memo_problems(text, tests, root=ROOT):
    found = sections(text)
    problems = [] if list(found) == SECTIONS else [f"memo sections {list(found)}, expected {SECTIONS}"]
    return (problems + exit_criteria_problems(text, tests, root) + quote_problems(text, root)
            + open_issue_problems(text, root) + lesson_problems(text, root) + prerequisite_problems(text, root))


PENDING_LINE = "Verdict: pending (`/phase-audit 0` has not run yet)"
BEFORE_AUDIT = ("PLANNED", "APPROVED", "IN-BUILD")


def wp_status(wp, root=ROOT):
    m = re.search(rf"^\| {re.escape(wp)} \| [^|]+\| ([A-Z-]+) \|", read("docs/progress/STATUS.md", root), re.M)
    return m.group(1) if m else None


def phase_audit_problems(text, root=ROOT):
    """FR-0.9-03: the memo links the phase audit report and states its verdict and audited commit as the report does.

    The approved order (docs/approvals/WP-0.9.md, Q1) runs /phase-audit 0 on this branch while WP-0.9 is IN-BUILD,
    before the report exists. Until then the memo must say exactly that the audit is pending; from READY-FOR-AUDIT
    on, a missing report is a problem."""
    body = sections(text).get("Phase audit", "")
    report = Path(root) / PHASE_AUDIT
    if f"`{PHASE_AUDIT}`" not in body:
        return [f"Phase audit does not link {PHASE_AUDIT}"]
    if not report.is_file():
        status = wp_status("WP-0.9", root)
        if status not in BEFORE_AUDIT:
            return [f"{PHASE_AUDIT} does not exist, and WP-0.9 is {status}"]
        if not re.search(rf"^{re.escape(PENDING_LINE)}$", body, re.M):
            return [f"{PHASE_AUDIT} does not exist yet, so Phase audit must say: {PENDING_LINE}"]
        return []
    if PENDING_LINE in body:
        return [f"{PHASE_AUDIT} exists, but the memo still says the audit is pending"]
    rtext = report.read_text(encoding="utf-8")
    verdict = re.search(r"^## Verdict: (PASS|FAIL)\b", rtext, re.M)
    commit = re.search(r"Commit audited: `?([0-9a-f]{7,40})`?", rtext)
    problems = []
    if not verdict or not commit:
        return [f"{PHASE_AUDIT} has no '## Verdict:' line or no 'Commit audited:'"]
    if not re.search(rf"^Verdict: {verdict.group(1)}$", body, re.M):
        problems.append(f"Phase audit does not state the report's verdict {verdict.group(1)}")
    if not re.search(rf"^Commit audited: `{commit.group(1)[:7]}[0-9a-f]*`$", body, re.M):
        problems.append(f"Phase audit does not state the report's audited commit {commit.group(1)[:12]}")
    if subprocess.run(["git", "merge-base", "--is-ancestor", commit.group(1), "HEAD"], cwd=root).returncode != 0:
        problems.append(f"the audited commit {commit.group(1)[:12]} is not an ancestor of HEAD")
    return problems
