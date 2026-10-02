"""WP-0.8 FR-0.8-05: options for the four targets (docs/decisions/TARGETS_OPTIONS.md); the owner decides.

The targets, the blueprint passages and the section headings cited are read from the committed sources
(docs/specs/sources/); the binomial thresholds are recomputed here from their definition.
"""
import re
from math import comb

from aqis_docs_testutil import SOURCES, headings, owner_blanks, read, sections, table_with

TARGETS_DOC = "docs/decisions/TARGETS_OPTIONS.md"
BLUEPRINT = SOURCES / "AQIS_Test_Lab_Blueprint.md"
BUILD_PLAN = SOURCES / "AQIS_Test_Lab_Build_Plan.md"
# FR-0.8-05's four targets: (section heading, target ID used in the approval's DECISION lines, option prefix,
# the blueprint "Quantitative Targets" bullet it comes from).
TARGETS = [
    ("Harm rate", "harm-rate", "HR", "Harm rate target"),
    ("Practical margin for model comparisons", "margin", "PM", "Practical margin"),
    ("Timing budget", "timing-budget", "TB", "Timing budget"),
    ("Gate escalation limit", "gate-escalation", "GE", "Gate escalation limit"),
]
OPTION_COLUMNS = ("Option", "Value", "What it gives", "What it costs", "Source")
# A citation names a source and one of its headings; it ends at ";", a table cell's "|", a "]" or the line's end.
CITATION_RE = re.compile(r"(Blueprint|Build Plan) § ([^;|\]\n]+?)\s*(?=[;|\]]|$)", re.M)
CHOOSING_RE = re.compile(r"\b(?:recommend(?:ed|s)?|preferred|prefer|chosen|choose option|selected|we suggest|"
                         r"best option|default option)\b", re.I)


def target_sections(text):
    found = sections(text, 2)
    return {heading: found[heading] for heading, _, _, _ in TARGETS if heading in found}


def options(body):
    return table_with(body, *OPTION_COLUMNS)


def choice_problems(text):
    """Must-catch 1 for the targets: why the document chooses (or ranks) an option, or [] when it does not."""
    problems = []
    found = target_sections(text)
    for heading, target, prefix, _ in TARGETS:
        body = found.get(heading)
        if body is None:
            problems.append(f"no section {heading!r}")
            continue
        lines = [l for l in body.splitlines() if l.startswith("**Decision:**")]
        expected = f"**Decision:** [OWNER DECIDES: {target} option]"
        if lines != [expected]:
            problems.append(f"{heading}: decision line {lines!r}, expected exactly [{expected!r}]")
    for m in CHOOSING_RE.finditer(text):
        problems.append(f"choosing or ranking wording: {m.group(0)!r}")
    return problems


def source_headings(path):
    return {line.lstrip("#").strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith("#")}


def test_FR_0_8_05_four_targets_each_with_2_or_3_options():
    text = read(TARGETS_DOC)
    found = target_sections(text)
    assert list(found) == [heading for heading, _, _, _ in TARGETS]
    for heading, _, prefix, _ in TARGETS:
        rows = options(found[heading])
        assert 2 <= len(rows) <= 3, heading
        assert [r["Option"] for r in rows] == [f"{prefix}-{c}" for c in "ABC"[:len(rows)]], heading
        assert len({r["Value"] for r in rows}) == len(rows), heading


def test_FR_0_8_05_every_option_has_trade_offs_and_a_citation():
    found = target_sections(read(TARGETS_DOC))
    for heading, _, _, bullet in TARGETS:
        for row in options(found[heading]):
            assert row["Value"] and len(row["What it gives"].split()) >= 5 and len(row["What it costs"].split()) >= 5, row
            cited = CITATION_RE.findall(row["Source"])
            assert ("Blueprint", "Quantitative Targets") in cited, (heading, row["Option"], cited)
        # The section quotes its blueprint target word for word.
        line = next(l for l in BLUEPRINT.read_text(encoding="utf-8").splitlines() if l.startswith(f"- {bullet}:"))
        assert line[2:].split(": ", 1)[1] in found[heading], heading


def test_FR_0_8_05_citations_name_sections_of_the_committed_blueprint():
    text = read(TARGETS_DOC)
    known = {"Blueprint": source_headings(BLUEPRINT), "Build Plan": source_headings(BUILD_PLAN)}
    cited = CITATION_RE.findall(text)
    assert cited
    for source, heading in cited:
        assert heading.strip() in known[source], (source, heading)


def test_FR_0_8_05_document_does_not_choose():
    assert choice_problems(read(TARGETS_DOC)) == []
    text = read(TARGETS_DOC)
    assert sorted(owner_blanks(text)) == sorted(f"{target} option" for _, target, _, _ in TARGETS)


def test_FR_0_8_05_choice_check_detects_a_filled_decision():
    text = read(TARGETS_DOC)
    blank = "[OWNER DECIDES: harm-rate option]"
    assert text.count(blank) == 1
    assert choice_problems(text.replace(blank, "HR-B")) != []
    assert choice_problems(text.replace("| HR-B |", "| HR-B (recommended) |", 1)) != []


def test_FR_0_8_05_decision_record_format_is_documented():
    # How the owner records a decision (approval question 7 (a)): one DECISION line per target in the approval.
    body = sections(read(TARGETS_DOC), 2)["How the owner decides"]
    assert "docs/approvals/WP-0.8.md" in body
    for _, target, prefix, _ in TARGETS:
        assert f"DECISION: {target} = {prefix}-" in body, target
    assert "DECISION: retention = " in body


def _max_wrong(n, target, alpha=0.05):
    """Largest number of wrong fillers among n for which an exact one-sided test still shows rate < target."""
    def cdf(k):
        return sum(comb(n, i) * target ** i * (1 - target) ** (n - i) for i in range(k + 1))
    k = -1
    while cdf(k + 1) <= alpha:
        k += 1
    return k


def test_FR_0_8_05_harm_rate_counts_recomputed():
    # Each harm-rate option states how many of the Build Plan's 500 rated filler turns may be wrong for the rate to
    # be shown below the target with 95 % confidence; recomputed here from the binomial distribution.
    assert "filler pack: 500 rated turns" in BUILD_PLAN.read_text(encoding="utf-8")
    rows = options(target_sections(read(TARGETS_DOC))["Harm rate"])
    for row in rows:
        target = float(re.fullmatch(r"below (\d+(?:\.\d+)?) ?%", row["Value"]).group(1)) / 100
        stated = re.search(r"at most (\d+) of 500", row["What it costs"] + " " + row["What it gives"])
        assert stated and int(stated.group(1)) == _max_wrong(500, target), (row["Option"], target)
