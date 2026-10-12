"""Unit tests for tools/progress/ids.py.

CAPABILITIES:
  CAP-PROGRESS-007: compute the next free ID as highest in use plus one
INPUTS AND OUTPUTS: scratch repositories built in tmp_path.
CONTRACTS: fragment formats v1; ID scheme in docs/process/CHANGE_CONTROL.md section 6.
INVARIANTS:
  - No network, no sleeps, no unseeded randomness.
NOT IN SCOPE:
  - Acceptance tests.
CHANGE LOG:
  2026-10-12 WP-1.0 WO-1.0-04 step 4 created.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.progress.ids import IdError, next_id


def _write(root: Path, rel: str, text: str = "x\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_B9_first_id_is_01(tmp_path: Path) -> None:
    assert next_id("BLK", "WP-2.1", tmp_path) == "BLK-2.1-01"
    assert next_id("DEC", "WP-2.2", tmp_path) == "DEC-2.2-01"
    assert next_id("DEBT", "WP-1.3", tmp_path) == "DEBT-1.3-01"
    assert next_id("WO", "WP-1.3", tmp_path) == "WO-1.3-01"


def test_B9_next_id_is_one_above_highest(tmp_path: Path) -> None:
    _write(tmp_path, "docs/progress/blockers.d/BLK-2.1-09.md")
    _write(tmp_path, "docs/progress/blockers.d/BLK-2.1-10.md")
    assert next_id("BLK", "WP-2.1", tmp_path) == "BLK-2.1-11"


def test_B9_gaps_are_never_refilled(tmp_path: Path) -> None:
    _write(tmp_path, "docs/progress/blockers.d/BLK-2.1-01.md")
    _write(tmp_path, "docs/progress/blockers.d/BLK-2.1-03.md")
    # BLK-2.1-02 is absent, but the gap is not handed out again.
    assert next_id("BLK", "WP-2.1", tmp_path) == "BLK-2.1-04"


def test_B9_searches_fragment_folders_and_work_orders(tmp_path: Path) -> None:
    _write(tmp_path, "docs/outsourcing/WO-1.3-02.md")
    _write(tmp_path, "docs/outsourcing/ledger.d/WO-1.3-05.md")
    assert next_id("WO", "WP-1.3", tmp_path) == "WO-1.3-06"
    _write(tmp_path, "docs/progress/debt.d/DEBT-1.3-04.md")
    assert next_id("DEBT", "WP-1.3", tmp_path) == "DEBT-1.3-05"
    _write(tmp_path, "docs/progress/decisions.d/DEC-1.3-07.md")
    assert next_id("DEC", "WP-1.3", tmp_path) == "DEC-1.3-08"


def test_B9_subfolders_count(tmp_path: Path) -> None:
    _write(tmp_path, "docs/progress/blockers.d/archive/BLK-2.1-04.md")
    assert next_id("BLK", "WP-2.1", tmp_path) == "BLK-2.1-05"


def test_B9_other_wps_and_kinds_do_not_count(tmp_path: Path) -> None:
    _write(tmp_path, "docs/progress/blockers.d/BLK-2.2-09.md")
    _write(tmp_path, "docs/progress/blockers.d/BLK-10.1-03.md")
    _write(tmp_path, "docs/progress/decisions.d/DEC-2.1-09.md")
    _write(tmp_path, "docs/progress/blockers.d/BLK-2.1-02.md")
    assert next_id("BLK", "WP-2.1", tmp_path) == "BLK-2.1-03"


def test_B9_kind_and_wp_are_validated(tmp_path: Path) -> None:
    with pytest.raises(IdError):
        next_id("XXX", "WP-2.1", tmp_path)
    with pytest.raises(IdError):
        next_id("blk", "WP-2.1", tmp_path)
    with pytest.raises(IdError):
        next_id("BLK", "wp-2.1", tmp_path)
    with pytest.raises(IdError):
        next_id("BLK", "WP-2", tmp_path)


def test_B9_ids_sort_numerically(tmp_path: Path) -> None:
    for number in (9, 10, 11):
        _write(tmp_path, f"docs/progress/blockers.d/BLK-2.1-{number:02d}.md")
    assert next_id("BLK", "WP-2.1", tmp_path) == "BLK-2.1-12"


def test_B9_ignores_non_md_and_non_matching_names(tmp_path: Path) -> None:
    _write(tmp_path, "docs/progress/blockers.d/BLK-2.1-09.txt")
    _write(tmp_path, "docs/progress/blockers.d/notes.md")
    _write(tmp_path, "docs/progress/blockers.d/BLK-2.1-1.md")  # one digit is not the scheme
    assert next_id("BLK", "WP-2.1", tmp_path) == "BLK-2.1-01"
