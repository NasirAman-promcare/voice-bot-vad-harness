"""WP-0.8 FR-0.8-04: filler library v0 (docs/fillers/FILLER_LIBRARY_v0.md).

Risk levels, blueprint examples and never-play rules are read from the committed blueprint
(docs/specs/sources/AQIS_Test_Lab_Blueprint.md), never from the library under test.
"""
import re

from aqis_docs_testutil import SOURCES, read, table_with

LIBRARY = "docs/fillers/FILLER_LIBRARY_v0.md"
BLUEPRINT = SOURCES / "AQIS_Test_Lab_Blueprint.md"
FILLER_COLUMNS = ("ID", "Level", "Text", "Intended use", "Never play when")
ID_RE = re.compile(r"fil-\d{3}")
CONTEXT_RE = re.compile(r"ctx-[a-z0-9-]+")
# The blueprint's three never-play rules, as the "Source" column of the context table names them.
RULE_SOURCE = "Blueprint, Never-Play Contexts, rule {}"
DRAFTED_SOURCE = "Drafted in WP-0.8 for owner review"


def blueprint_levels():
    """{level number: (name, allowed when, [example texts])} from the blueprint's risk ladder."""
    levels = {}
    for m in re.finditer(r"^- Level (\d)\. ([^:]+): (.+?) Examples: (.+?) Allowed when: (.+)$",
                         BLUEPRINT.read_text(encoding="utf-8"), re.M):
        levels[m.group(1)] = (m.group(2).strip(), m.group(5).strip(), re.findall(r'"([^"]+)"', m.group(4)))
    return levels


def blueprint_rules():
    body = BLUEPRINT.read_text(encoding="utf-8").split("### Never-Play Contexts", 1)[1].split("\n## ", 1)[0]
    return [line[2:].strip() for line in body.splitlines() if line.startswith("- ")]


def fillers(text):
    return table_with(text, *FILLER_COLUMNS)


def contexts(text):
    return {row["Context ID"]: row for row in table_with(text, "Context ID", "Never play when", "Source")}


def filler_contexts(row):
    return CONTEXT_RE.findall(row["Never play when"])


def filler_problems(text):
    """Must-catch 2 for every filler: a risk level that is one of the four, and at least one never-play context."""
    problems = []
    for row in fillers(text):
        if row["Level"] not in blueprint_levels():
            problems.append(f"{row['ID']}: risk level {row['Level']!r} is not one of the blueprint's four")
        if not filler_contexts(row):
            problems.append(f"{row['ID']}: no context where it must never play")
    return problems


def test_FR_0_8_04_library_has_about_20_fillers():
    assert 18 <= len(fillers(read(LIBRARY))) <= 22                      # "about 20" (PLAN.md, "Filler library")


def test_FR_0_8_04_risk_levels_are_the_blueprint_four_and_all_used():
    text = read(LIBRARY)
    expected = blueprint_levels()
    assert sorted(expected) == ["0", "1", "2", "3"]
    table = table_with(text, "Level", "Name", "Commits to", "Allowed when", "Source")
    assert {r["Level"]: (r["Name"], r["Allowed when"]) for r in table} == \
        {n: (name, allowed) for n, (name, allowed, _) in expected.items()}
    assert {r["Level"] for r in fillers(text)} == set(expected)


def test_FR_0_8_04_every_filler_has_id_text_use_and_risk_level():
    text = read(LIBRARY)
    for row in fillers(text):
        assert ID_RE.fullmatch(row["ID"]), row
        assert row["Text"] and row["Intended use"], row
    assert [p for p in filler_problems(text) if "risk level" in p] == []


def test_FR_0_8_04_every_filler_has_a_never_play_context():
    assert [p for p in filler_problems(read(LIBRARY)) if "never play" in p] == []


def test_FR_0_8_04_ids_and_texts_unique():
    rows = fillers(read(LIBRARY))
    ids = [r["ID"] for r in rows]
    assert ids == sorted(set(ids)) and ids == [f"fil-{i:03d}" for i in range(1, len(ids) + 1)]
    texts = [r["Text"].strip('"').lower() for r in rows]
    assert len(set(texts)) == len(texts)


def test_FR_0_8_04_every_context_used_is_defined():
    text = read(LIBRARY)
    defined = contexts(text)
    used = {c for row in fillers(text) for c in filler_contexts(row)}
    assert used <= set(defined), used - set(defined)
    assert set(defined) <= used, set(defined) - used                     # no context defined but never used
    for cid, row in defined.items():
        assert CONTEXT_RE.fullmatch(cid) and row["Never play when"], cid
        source = row["Source"]
        assert source == DRAFTED_SOURCE or source.startswith("Blueprint, "), (cid, source)


def test_FR_0_8_04_blueprint_examples_are_in_the_library_at_their_level():
    rows = fillers(read(LIBRARY))
    at = {r["Text"].strip('"'): r["Level"] for r in rows}
    for level, (_, _, examples) in blueprint_levels().items():
        assert examples, level
        for example in examples:
            assert at.get(example) == level, (example, level)


def test_FR_0_8_04_blueprint_never_play_rules_are_encoded():
    rules = blueprint_rules()
    assert len(rules) == 3 and "Level 2" in rules[0] and "Level 3" in rules[1] and "low" in rules[2], rules
    text = read(LIBRARY)
    defined = contexts(text)
    by_rule = {n: {cid for cid, row in defined.items() if row["Source"] == RULE_SOURCE.format(n)} for n in (1, 2, 3)}
    # Rule 1 names negative/distressed callers and complaints; rule 2 direct questions, yes/no answers and digit
    # strings; rule 3 low model confidence.
    assert len(by_rule[1]) == 2 and len(by_rule[2]) == 3 and len(by_rule[3]) == 1, by_rule
    for row in fillers(text):
        listed = set(filler_contexts(row))
        if row["Level"] == "2" and "positive" in row["Intended use"]:
            assert by_rule[1] <= listed, row["ID"]                       # rule 1: cheerful filler, upset caller
        if row["Level"] == "3":
            assert by_rule[2] <= listed, row["ID"]                       # rule 2
        if row["Level"] in ("2", "3"):
            assert by_rule[3] <= listed, row["ID"]                       # rule 3: only Level 0 or 1 when unsure
        if row["Level"] in ("0", "1"):
            assert not (by_rule[3] & listed), row["ID"]                  # Level 0 and 1 are the fallback


def test_FR_0_8_04_checks_detect_missing_level_or_context():
    # The must-catch checks are not empty: edited copies with one filler's level or contexts removed fail them.
    text = read(LIBRARY)
    first = fillers(text)[0]
    line = next(l for l in text.splitlines() if l.startswith(f"| {first['ID']} |"))
    cells = line.split("|")
    no_level = cells.copy()
    no_level[2] = "  "
    no_context = cells.copy()
    no_context[-2] = " none "
    assert any("risk level" in p for p in filler_problems(text.replace(line, "|".join(no_level))))
    assert any("never play" in p for p in filler_problems(text.replace(line, "|".join(no_context))))
