"""Shared helpers for the WP-0.8 document tests: Markdown sections and tables, owner blanks, words and sentences.

The documents are plain Markdown with fixed headings and pipe tables (docs/progress/WP-0.8/PLAN.md, "How the tests
read the documents"). These helpers read only that much Markdown, and fail loudly on anything else they are asked for.
"""
import re
from pathlib import Path

from aqis_testutil import ROOT

# An owner decision left open in a document (PLAN.md, "Owner blanks"): [OWNER DECIDES: <what>].
OWNER_BLANK_RE = re.compile(r"\[OWNER DECIDES: ([^\]\n]+)\]")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
HEADING_RE = re.compile(r"^(#{1,6}) +(.+?) *$")
FIELD_LINE_RE = re.compile(r"_{4,}")          # a blank line a person fills in by hand: "Name: ________"
SOURCES = ROOT / "docs" / "specs" / "sources"
APPROVAL = ROOT / "docs" / "approvals" / "WP-0.8.md"


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def visible(text):
    """The text a reader sees: HTML comments removed."""
    return COMMENT_RE.sub("", text)


def headings(text, level):
    """The headings of exactly `level` (2 for '## ...'), in order."""
    out = []
    for line in visible(text).splitlines():
        m = HEADING_RE.match(line)
        if m and len(m.group(1)) == level:
            out.append(m.group(2))
    return out


def sections(text, level):
    """{heading: body} for the headings of `level`; a body runs to the next heading of the same or a higher level."""
    out, current, body = {}, None, []
    for line in visible(text).splitlines():
        m = HEADING_RE.match(line)
        if m and len(m.group(1)) <= level:
            if current is not None:
                out[current] = "\n".join(body).strip()
            current, body = (m.group(2), []) if len(m.group(1)) == level else (None, [])
            if current is not None and current in out:
                raise AssertionError(f"heading {current!r} appears twice")
            continue
        if current is not None:
            body.append(line)
    if current is not None:
        out[current] = "\n".join(body).strip()
    return out


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def tables(text):
    """Every pipe table in the text as a list of {header: cell} rows (the header row and its rule are not rows)."""
    found, lines = [], visible(text).splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("|") and i + 1 < len(lines) and re.fullmatch(r"\|?[\s:|-]+\|?",
                                                                                     lines[i + 1].strip()):
            header = _cells(lines[i])
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = _cells(lines[i])
                if len(cells) != len(header):
                    raise AssertionError(f"table row has {len(cells)} cells, header has {len(header)}: {lines[i]}")
                rows.append(dict(zip(header, cells)))
                i += 1
            found.append(rows)
            continue
        i += 1
    return found


def table_with(text, *columns):
    """The one table whose header holds all `columns`."""
    matches = [t for t in tables(text) if t and all(c in t[0] for c in columns)]
    if len(matches) != 1:
        raise AssertionError(f"expected one table with columns {columns}, found {len(matches)}")
    return matches[0]


def owner_blanks(text):
    return OWNER_BLANK_RE.findall(visible(text))


def words(text):
    """Words a reader sees (comments, Markdown markers and fill-in lines are not words)."""
    plain = FIELD_LINE_RE.sub(" ", visible(text))
    return re.findall(r"[A-Za-z0-9@][A-Za-z0-9@'’./()-]*", plain)


def sentences(text):
    """Sentences of the visible prose: headings and fill-in lines are left out; a line break ends a sentence."""
    out = []
    for line in visible(text).splitlines():
        line = line.strip()
        if not line or HEADING_RE.match(line) or FIELD_LINE_RE.search(line):
            continue
        line = re.sub(r"^(?:[-*]|\d+\.)\s+(?:\[ \]\s+)?", "", line)       # list markers and tick boxes
        for part in re.split(r"(?<=[.!?])\s+", line):
            if words(part):
                out.append(part)
    return out
