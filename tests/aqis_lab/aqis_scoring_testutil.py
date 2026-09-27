"""Shared helpers for the WP-0.3 scoring tests (not a test module).

Everything here is written independently of aqis_lab/scoring/: the text generator, the Markdown table
parser for docs/contracts/, the textbook edit distance and the CSV writers never call the code under test.
"""
import csv
import random
import re
import subprocess
import sys
from pathlib import Path

from aqis_testutil import ROOT

NORMALISATION_DOC = ROOT / "docs" / "contracts" / "NORMALISATION.md"
SCORE_TABLE_DOC = ROOT / "docs" / "contracts" / "SCORE_TABLE.md"
FIXTURES = ROOT / "tests" / "aqis_lab" / "fixtures" / "scoring"
REF_FIXTURE = FIXTURES / "ref.csv"
HYP_FIXTURE = FIXTURES / "hyp.csv"
RUN_CARD_FIXTURE = ROOT / "tests" / "aqis_lab" / "fixtures" / "contracts" / "valid_run_card.json"

# Approved in docs/approvals/WP-0.3.md (plan questions 2 and 3): the pinned package and Whisper's own filler list.
PINNED_WHISPER_NORMALIZER = "0.1.1"
PINNED_JIWER = "4.0.0"
WHISPER_FILLERS = ("hmm", "mm", "mhm", "mmm", "uh", "um")
MAIN_NAME = "aqis-whisper-english"
KEEP_NAME = "aqis-whisper-english-keep-disfluencies"
NORMALISER_VERSION = "1+whisper-normalizer-0.1.1"

# Tokens chosen to exercise every Whisper rule: number words, ordinals, currency and symbols, fillers,
# brackets, contractions, abbreviations, British spellings, hyphens, letters and diacritics.
TEXT_VOCABULARY = (
    "one two three four five six seven eight nine ten eleven twelve thirteen twenty thirty forty fifty "
    "ninety hundred thousand million billion first second third fourth twentieth hundredth and point minus "
    "plus oh o zero dollars dollar cents pounds euros percent a half quarter the of to at in $ £ € % - . , ' "
    "1 2 10 01 1.5 $1 £3.25 €10 1st 2nd 21st 1s 3:30 7:30 10.30am p.m. uh um hmm mm mhm mmm er erm ah "
    "[laughs] (inaudible) won't it's can't i'm they'd've y'all ain't gonna o'clock mr. dr. st. colour "
    "organise travelling centre u.s. a. b c. e-mail twenty-one well-known mother-in-law naïve café hello "
    "world okay yes no i think well so like you know mcdonald's o'brien iphone nasa"
).split()


def generated_texts(seed, count, min_tokens=1, max_tokens=8):
    """Seeded raw texts built from TEXT_VOCABULARY, with random casing and punctuation spacing."""
    rng = random.Random(seed)
    texts = []
    for _ in range(count):
        words = []
        for _ in range(rng.randint(min_tokens, max_tokens)):
            word = rng.choice(TEXT_VOCABULARY)
            roll = rng.random()
            if roll < 0.15:
                word = word.upper()
            elif roll < 0.3:
                word = word.capitalize()
            words.append(word)
        texts.append(rng.choice((" ", "  ", " \t")).join(words))
    return texts


def markdown_tables(text):
    """Every pipe table in a Markdown text as (heading, header cells, rows of cells, raw row lines).

    Cells are split on unescaped '|' and stripped; '\\|' becomes '|'. The heading is the nearest
    preceding '#' line.
    """
    tables, heading, lines, i = [], "", text.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|(\s*:?-+:?\s*\|)+\s*$", lines[i + 1]):
            header = split_row(line)
            rows, raw = [], []
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(split_row(lines[i]))
                raw.append(lines[i])
                i += 1
            tables.append((heading, header, rows, raw))
            continue
        i += 1
    return tables


def split_row(line):
    body = line.strip()
    assert body.startswith("|") and body.endswith("|"), f"not a table row: {line!r}"
    cells = re.split(r"(?<!\\)\|", body[1:-1])
    return [cell.strip().replace("\\|", "|") for cell in cells]


def code_span(cell):
    """The text inside a single Markdown code span `...`; '(empty)' means the empty text."""
    if cell == "(empty)":
        return ""
    m = re.fullmatch(r"`(.*)`", cell)
    assert m, f"expected one code span or (empty), got {cell!r}"
    return m.group(1)


def textbook_distance(a, b):
    """Plain Wagner-Fischer unit-cost edit distance (independent of aqis_lab.scoring.wer)."""
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def write_csv(path, header, rows):
    """Write a UTF-8 CSV with the csv module (independent of the command's reader)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    return path


def run_score(*args, env=None, cwd=None):
    """Run `python -m aqis_lab score ...` as a subprocess with the running interpreter."""
    return subprocess.run([sys.executable, "-m", "aqis_lab", "score", *map(str, args)], cwd=cwd or ROOT,
                          capture_output=True, text=True, timeout=300, env=env)
