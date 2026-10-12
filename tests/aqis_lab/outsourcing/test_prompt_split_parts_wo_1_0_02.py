"""Claude's fix for WO-1.0-02 B3 item 4 with WO-1.0-11 B13 (FR-1.0-02), written first: FIX-B3-split-siblings.

WO-1.0-11 B13 splits a cut-off part into one request per file, in the part's order, each its own part. On 2026-10-12,
WO-1.0-03 step 5 was split into 5.1 (`tools/index/impact.py`) and 5.2 (`tests/aqis_lab/index/test_impact.py`). 5.1
was accepted, but the 5.2 request did not show `impact.py`: only outputs of lower-numbered steps were included. The
model guessed `ImpactResult` twice and then returned QUESTIONS. The step block promises "the tests you return must pass
with only the files above and the files you return now", so a split part must see the files of its step that were
accepted before it, which are the step's files that come before the part's first file.
"""
from __future__ import annotations

from pathlib import Path

from tools.outsourcing.prompt import step_request
from tools.outsourcing.records import StepPart
from tools.outsourcing.workorder import load_work_order, plan_steps

FIRST, SECOND, THIRD = "tools/demo/alpha.py", "tests/aqis_lab/demo/test_alpha.py", "tools/demo/beta.py"


def scratch(root: Path) -> tuple:
    for rel, text in {
        "docs/process/PROTECTED_PATHS.txt": "[LAB-OWNED]\ntools/**\ntests/aqis_lab/**\n",
        "docs/process/outsourcing/FOUNDATION.md": "Foundation",
        "docs/process/outsourcing/templates/RETURN_FORMAT.md": "Format",
        "tests/aqis_lab/demo/test_ro.py": "def test_x():\n    pass\n",
        FIRST: '"""Alpha."""\n\n\ndef alpha_marker_fn(value: int) -> int:\n    return value\n',
    }.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    order_file = root / "order.md"
    order_file.write_text(
        "---\nid: WO-9.9-01\nwp: WP-9.9\ntitle: t\nmodel: default\nchannel: api\n"
        "attempt_budget: 3\nrisk_tier: T1\nmax_output_tokens: 100\n"
        f"context: []\noutputs:\n  - {FIRST}\n  - {SECOND}\n  - {THIRD}\n"
        f"steps:\n  - {FIRST}, {SECOND}\n  - {THIRD}\n"
        "read_only_tests:\n  - tests/aqis_lab/demo/test_ro.py\n"
        "allowed_dependencies:\n  - stdlib\nverify:\n  - pytest\n---\nbody",
        encoding="utf-8",
    )
    order = load_work_order(order_file, root)
    return order, plan_steps(order)


def test_FR_1_0_02_fix_split_part_sees_the_step_files_accepted_before_it(tmp_path):
    order, plan = scratch(tmp_path)
    request = step_request(order, plan, StepPart("1.2", (SECOND,)), tmp_path)
    text = request.chat.turns[0].text
    assert f"=== ACCEPTED INTERFACE: {FIRST} ===" in text and "alpha_marker_fn" in text
    assert FIRST in request.sent_paths
    assert f"Return exactly these files, each complete: {SECOND}." in text


def test_FR_1_0_02_fix_first_split_part_and_whole_step_show_no_sibling(tmp_path):
    order, plan = scratch(tmp_path)
    (tmp_path / SECOND).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / SECOND).write_text("def test_left_over():\n    pass\n", encoding="utf-8")
    for part in (StepPart("1.1", (FIRST,)), StepPart("1", (FIRST, SECOND))):
        request = step_request(order, plan, part, tmp_path)
        assert "=== ACCEPTED" not in request.chat.turns[0].text
        assert SECOND not in request.sent_paths and FIRST in part.paths
