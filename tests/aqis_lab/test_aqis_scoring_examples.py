"""FR-0.3-02: every example in docs/contracts/NORMALISATION.md is a test, for both variants."""
import re
from collections import Counter

import pytest

from aqis_scoring_testutil import NORMALISATION_DOC, code_span, markdown_tables

from aqis_lab.scoring.normalise import normalise, normalise_keep_disfluencies

EXAMPLES_HEADER = ["ID", "Category", "Input", "Main", "Disfluency-aware"]
# The categories FR-0.3-02 names; each must have at least 3 examples.
SPEC_CATEGORIES = ("numbers", "currency", "dates", "times", "ordinals", "contractions", "hyphens", "disfluencies",
                   "casing", "punctuation", "spelled-out letters")


def documented_examples():
    tables = [t for t in markdown_tables(NORMALISATION_DOC.read_text(encoding="utf-8")) if t[0] == "Examples"]
    assert len(tables) == 1, "NORMALISATION.md needs exactly one table under the heading 'Examples'"
    _, header, rows, _ = tables[0]
    assert header == EXAMPLES_HEADER, header
    examples = []
    for cells in rows:
        assert len(cells) == 5, cells
        examples.append((cells[0], cells[1], code_span(cells[2]), code_span(cells[3]), code_span(cells[4])))
    return examples


EXAMPLES = documented_examples()


@pytest.mark.parametrize("example_id, category, text, main, keep", EXAMPLES, ids=[e[0] for e in EXAMPLES])
def test_FR_0_3_02_documented_example(example_id, category, text, main, keep):
    assert normalise(text) == main
    assert normalise_keep_disfluencies(text) == keep
    assert normalise(main) == main
    assert normalise_keep_disfluencies(keep) == keep


def test_FR_0_3_02_at_least_30_examples_cover_every_category():
    assert len(EXAMPLES) >= 30
    ids = [e[0] for e in EXAMPLES]
    assert len(ids) == len(set(ids)), [i for i, n in Counter(ids).items() if n > 1]
    per_category = Counter(e[1] for e in EXAMPLES)
    for category in SPEC_CATEGORIES:
        assert per_category[category] >= 3, (category, per_category[category])
    # The disfluency examples must show the two variants differing.
    assert any(e[3] != e[4] for e in EXAMPLES if e[1] == "disfluencies")


def test_FR_0_3_02_parser_reads_every_table_row():
    text = NORMALISATION_DOC.read_text(encoding="utf-8")
    section = re.search(r"^## Examples\n(.*?)(?=^## )", text, re.M | re.S).group(1)
    table_lines = [line for line in section.splitlines() if line.startswith("|")]
    # Header and separator plus one line per example: nothing is dropped by the parser.
    assert len(table_lines) == len(EXAMPLES) + 2
    assert all(line.count("|") == 6 for line in table_lines), [line for line in table_lines if line.count("|") != 6]
