"""Claude's fix for BLK-1.0-07 (owner answer: option 1), written before the fix (FR-1.0-01, WO-1.0-01 B5 amended).

RETURN_FORMAT.md on `main` now says: "The relay removes one code fence that wraps the whole answer; anything else
outside the blocks is refused." codestral-2508 wraps every reply in ```` ```text ```` … ```` ``` ````. `parse_bundle`
removes exactly one such pair when it encloses the whole reply and parses the inside as strictly as before; any other
text outside the blocks, a second fence, or an unmatched fence stays a `BundleError`.
"""
from __future__ import annotations

import pytest

from tests.aqis_lab.outsourcing.test_acceptance_wo_1_0_01 import OUTPUTS3, bundle_text, content, mod

FILES = {path: content(path) for path in OUTPUTS3}
PLAIN = bundle_text(FILES)


def parsed(text: str):
    return mod("bundle").parse_bundle(text)


@pytest.mark.parametrize("opening, closing, around", [
    ("```text", "```", ""),
    ("```", "```", ""),
    ("````markdown", "````", ""),
    ("```text", "```", "\n\n"),
    ("  ```text  ", " ``` ", ""),
], ids=["text-fence", "bare-fence", "four-backticks", "blank-lines-around", "indented-markers"])
def test_FR_1_0_01_one_fence_wrapping_the_whole_reply_is_removed(opening, closing, around):
    fenced = f"{around}{opening}\n{PLAIN}{closing}\n{around}"
    assert parsed(fenced) == parsed(PLAIN)
    assert [path for path, _ in parsed(fenced).files] == list(OUTPUTS3)


@pytest.mark.parametrize("text", [
    "Here are the files:\n```text\n" + PLAIN + "```\n",
    "```text\n" + PLAIN + "```\nHope this helps.\n",
    "```text\n```text\n" + PLAIN + "```\n```\n",
    "```text\n" + PLAIN,
    PLAIN + "```\n",
    "```text\n" + PLAIN + "````\n",
    "```python\n" + PLAIN + "~~~\n",
], ids=["text-before-fence", "text-after-fence", "two-fences", "unclosed-fence", "closing-only",
        "mismatched-backticks", "mismatched-fence-kind"])
def test_FR_1_0_01_other_text_or_fences_outside_the_blocks_stay_refused(text):
    with pytest.raises(mod("bundle").BundleError):
        parsed(text)


def test_FR_1_0_01_fence_inside_a_file_block_is_untouched_by_the_outer_rule():
    inner = {OUTPUTS3[0]: "```python\n" + content(OUTPUTS3[0]) + "```\n", OUTPUTS3[1]: content(OUTPUTS3[1]),
             OUTPUTS3[2]: content(OUTPUTS3[2])}
    plain = bundle_text(inner)
    assert parsed("```text\n" + plain + "```\n") == parsed(plain)
