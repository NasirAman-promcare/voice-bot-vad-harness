"""Allocate the next free ID for a kind and work package.

CAPABILITIES:
  CAP-PROGRESS-007: compute the next free ID as highest in use plus one
    [tests: test_B9_next_id_is_one_above_highest, test_B9_gaps_are_never_refilled,
    test_B9_first_id_is_01, test_B9_searches_fragment_folders_and_work_orders,
    test_B9_subfolders_count, test_B9_other_wps_and_kinds_do_not_count,
    test_B9_kind_and_wp_are_validated, test_B9_ids_sort_numerically,
    test_B9_ignores_non_md_and_non_matching_names]
INPUTS AND OUTPUTS: kind, WP ID and repository root; returns the next free ID string.
CONTRACTS: fragment formats v1 (docs/process/templates/FRAGMENTS.md); ID scheme in
  docs/process/CHANGE_CONTROL.md section 6.
INVARIANTS:
  - Gaps are never refilled: the next number is one above the highest in use.
  - Iteration over directories is sorted.
  - Reading IDs never writes to the repository.
NOT IN SCOPE:
  - Parsing, linting, rendering and migration (separate modules).
CHANGE LOG:
  2026-10-12 WP-1.0 WO-1.0-04 step 4 created.
  2026-10-12 WP-1.0 WO-1.0-04 fix 1: the ID pattern requires the two-digit
  sequence number of the <KIND>-<n>.<n>-<nn> scheme."""
from __future__ import annotations

import re
from pathlib import Path

__all__ = ["KIND_FOLDERS", "IdError", "next_id"]

# Folders scanned per kind, relative to the repository root. Each kind's own
# fragment folder comes first; every kind also counts work orders.
KIND_FOLDERS: dict[str, tuple[str, ...]] = {
    "BLK": ("docs/progress/blockers.d",),
    "DEC": ("docs/progress/decisions.d",),
    "DEBT": ("docs/progress/debt.d",),
    "WO": ("docs/outsourcing",),
}

_WORK_ORDER_FOLDER = "docs/outsourcing"

_KIND_PATTERN = re.compile(r"^[A-Z]+$")
_WP_PATTERN = re.compile(r"^WP-(\d+)\.(\d+)$")
# New-style IDs follow <KIND>-<n>.<n>-<nn>: the sequence number has at least
# two digits, so a one-digit file name like BLK-2.1-1.md is not an ID in use.
_ID_PATTERN_TEMPLATE = r"^{kind}-(\d+)\.(\d+)-(\d\d\d*)\.md$"


class IdError(Exception):
    """The kind or WP given for a new ID is not usable."""


def _numbers_in_use(kind: str, wp: str, repo_root: Path) -> list[int]:
    """Collect every sequence number of `kind`-`wp` IDs under the known folders."""
    match = _WP_PATTERN.fullmatch(wp)
    if match is None:
        raise IdError(f"new-id: WP {wp!r} does not match WP-<n>.<n>")
    phase, wp_number = match.group(1), match.group(2)
    id_pattern = re.compile(_ID_PATTERN_TEMPLATE.format(kind=re.escape(kind)))
    folders = list(KIND_FOLDERS[kind])
    if kind != "WO":
        folders.append(_WORK_ORDER_FOLDER)
    numbers: list[int] = []
    for folder in folders:
        base = repo_root / folder
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            found = id_pattern.match(path.name)
            if found and found.group(1) == phase and found.group(2) == wp_number:
                numbers.append(int(found.group(3)))
    return numbers


def next_id(kind: str, wp: str, repo_root: Path) -> str:
    """Return the next free ID for `kind` and `wp`: one above the highest in use.

    Every folder named for the kind (including subfolders) plus the work order
    folder is scanned. Gaps are never refilled; with none in use the ID ends in 01.
    """
    if kind not in KIND_FOLDERS or _KIND_PATTERN.fullmatch(kind) is None:
        known = ", ".join(sorted(KIND_FOLDERS))
        raise IdError(f"new-id: kind {kind!r} is not one of {known}")
    numbers = _numbers_in_use(kind, wp, repo_root)
    match = _WP_PATTERN.fullmatch(wp)
    if match is None:  # pragma: no cover - _numbers_in_use already checked
        raise IdError(f"new-id: WP {wp!r} does not match WP-<n>.<n>")
    highest = max(numbers, default=0)
    return f"{kind}-{match.group(1)}.{match.group(2)}-{highest + 1:02d}"
