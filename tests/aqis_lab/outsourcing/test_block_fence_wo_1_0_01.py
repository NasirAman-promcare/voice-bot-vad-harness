"""Claude's fix for BLK-1.0-08 (owner answer: option 1), written before the fix (FR-1.0-01, WO-1.0-01 B5 amended).

RETURN_FORMAT.md on `main` now also says: "It also removes a code fence wrapped tightly around a single block: a
fence line directly before the block's opening marker and its closing line directly after the block's END marker."
codestral-2508 fences every block that way. `parse_bundle` removes each such pair (same backticks, no line between
fence and marker); the outer-fence rule then applies to what is left. A fence that is not part of an exact pair stays
in place and is refused as text outside the blocks.
"""
from __future__ import annotations

import pytest

from tests.aqis_lab.outsourcing.test_acceptance_wo_1_0_01 import OUTPUTS3, bundle_text, content, mod

FILES = {path: content(path) for path in OUTPUTS3}
PLAIN = bundle_text(FILES)


def parsed(text: str):
    return mod("bundle").parse_bundle(text)


def blocks(text: str) -> list[list[str]]:
    """Split a plain bundle into its blocks (each a list of lines from opening marker to END marker)."""
    out, current = [], None
    for line in text.splitlines():
        if current is None:
            current = [line]
        else:
            current.append(line)
        if line.startswith("=== END "):
            out.append(current)
            current = None
    assert current is None
    return out


def fenced_per_block(text: str, opening="```text", closing="```", gap="\n", which=None) -> str:
    parts = []
    for n, block in enumerate(blocks(text)):
        if which is None or n in which:
            parts.append(f"{opening}\n" + "\n".join(block) + f"\n{closing}")
        else:
            parts.append("\n".join(block))
    return gap.join(parts) + "\n"


@pytest.mark.parametrize("kwargs", [
    {},
    {"gap": "\n\n"},
    {"opening": "```", "closing": "```"},
    {"opening": "````markdown", "closing": "````"},
    {"opening": "  ```text", "closing": "```  "},
    {"which": {0, 2}},
], ids=["codestral-shape", "blank-line-between-blocks", "bare-fences", "four-backticks", "indented-fences",
        "some-blocks-fenced"])
def test_FR_1_0_01_fence_tight_around_each_block_is_removed(kwargs):
    text = fenced_per_block(PLAIN, **kwargs)
    assert parsed(text) == parsed(PLAIN)
    assert [path for path, _ in parsed(text).files] == list(OUTPUTS3)


def test_FR_1_0_01_outer_fence_and_block_fences_together():
    assert parsed("```text\n" + fenced_per_block(PLAIN) + "```\n") == parsed(PLAIN)


def test_FR_1_0_01_questions_block_with_tight_fence():
    plain = "=== QUESTIONS ===\n1. Which file holds the table?\n=== END QUESTIONS ===\n"
    assert parsed("```text\n" + plain + "```\n") == parsed(plain)
    assert len(parsed(plain).questions) == 1 and "Which file holds the table?" in parsed(plain).questions[0]


def loose(text: str, before: str, after: str) -> str:
    first = blocks(PLAIN)[0]
    rest = PLAIN.split("=== END MANIFEST ===\n", 1)[1]
    return before + "\n".join(first) + after + rest


@pytest.mark.parametrize("text", [
    loose(PLAIN, "```text\n\n", "\n```\n"),
    loose(PLAIN, "```text\n", "\n\n```\n"),
    loose(PLAIN, "```text\n", "\n"),
    loose(PLAIN, "", "\n```\n"),
    loose(PLAIN, "```text\n", "\n````\n"),
    loose(PLAIN, "Here is the manifest:\n```text\n", "\n```\n"),
    fenced_per_block(PLAIN) + "Hope this helps.\n",
    fenced_per_block(PLAIN).replace("```text\n=== FILE", "```text\n```text\n=== FILE", 1),
], ids=["blank-after-opening-fence", "blank-before-closing-fence", "opening-without-closing", "closing-without-opening",
        "mismatched-backticks", "prose-before-fence", "prose-after-blocks", "doubled-opening-fence"])
def test_FR_1_0_01_fences_not_tight_or_unmatched_stay_refused(text):
    with pytest.raises(mod("bundle").BundleError):
        parsed(text)


def test_FR_1_0_01_fence_lines_inside_a_file_block_are_content_not_block_fences():
    inner = dict(FILES)
    inner[OUTPUTS3[0]] = "```python\n" + content(OUTPUTS3[0]) + "```\n"
    plain = bundle_text(inner)
    assert parsed(fenced_per_block(plain)) == parsed(plain)
