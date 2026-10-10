"""Bundle importer writing parsed files to disk atomically.

CAPABILITIES:
  CAP-OUTSOURCING-006: write bundle files atomically with mode and expected checks [tests: test_FR_1_0_01_valid_bundle_imports_every_file_exactly, test_FR_1_0_01_mc01_path_outside_outputs_fails_import_and_writes_nothing, test_FR_1_0_01_mc01_read_only_test_in_bundle_is_refused_and_unchanged, test_FR_1_0_01_mc01_path_outside_expected_fails_fix_import, test_importer.py]
INPUTS AND OUTPUTS: ImportedFile, ImportReport, QuestionsReturned, ImportRefused, import_bundle.
CONTRACTS: RETURN_FORMAT.md specification.
INVARIANTS:
  - Atomic writes: nothing is written unless every check passes.
  - Refuses to write outside outputs or follow symlinks out of repo.
NOT IN SCOPE:
  - Git commit operations.
CHANGE LOG:
  2026-10-10 WO-1.0-01 created.
"""
from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from tools.outsourcing.bundle import Bundle
from tools.outsourcing.paths import normalise
from tools.outsourcing.workorder import WorkOrder

__all__ = ["QuestionsReturned", "ImportRefused", "ImportedFile", "ImportReport", "import_bundle"]


class QuestionsReturned(Exception):
    """Raised when an import is attempted on a bundle with questions."""


class ImportRefused(Exception):
    """Raised when an import is refused due to scope or safety checks."""


@dataclass(frozen=True)
class ImportedFile:
    path: str
    bytes: int
    lines: int
    sha256: str


@dataclass(frozen=True)
class ImportReport:
    files: tuple[ImportedFile, ...]


def import_bundle(
    bundle: Bundle,
    order: WorkOrder,
    repo_root: str | Path,
    mode: str = "first",
    dry_run: bool = False,
    expected: set[str] | None = None,
) -> ImportReport:
    root = Path(repo_root).resolve()

    if bundle.questions:
        raise QuestionsReturned("Bundle contains questions; import stopped")

    if mode not in ("first", "fix"):
        raise ImportRefused(f"Invalid mode: {mode!r} (expected 'first' or 'fix')")

    expected_set = set(expected) if expected is not None else set(order.outputs)
    order_outputs_set = set(order.outputs)

    bundle_files_dict = dict(bundle.files)
    bundle_paths = set(bundle_files_dict.keys())

    # Check that all bundle paths are within order.outputs
    outside_order = bundle_paths - order_outputs_set
    if outside_order:
        raise ImportRefused(f"Bundle files outside order outputs: {sorted(outside_order)}")

    # Check mode requirements
    if mode == "first":
        if bundle_paths != expected_set:
            diff_missing = expected_set - bundle_paths
            diff_extra = bundle_paths - expected_set
            raise ImportRefused(f"First mode requires exact match for expected. Missing: {sorted(diff_missing)}, Extra: {sorted(diff_extra)}")
    elif mode == "fix":
        if not bundle_paths:
            raise ImportRefused("Fix mode requires at least one file")
        extra_paths = bundle_paths - expected_set
        if extra_paths:
            raise ImportRefused(f"Fix mode received files outside expected set: {sorted(extra_paths)}")

    # Pre-validation of target paths
    staged_writes: list[tuple[Path, str, str]] = []

    for rel_path, content in bundle.files:
        norm_p = normalise(rel_path)
        target = root / norm_p

        # Symlink escape check
        try:
            resolved_parent = target.parent.resolve()
            if not resolved_parent.is_relative_to(root) and resolved_parent != root:
                raise ImportRefused(f"Path resolves outside repository root via symlink: {rel_path!r}")
        except OSError as exc:
            raise ImportRefused(f"Cannot resolve path for {rel_path!r}: {exc}") from exc

        if target.exists() and target.is_dir():
            raise ImportRefused(f"Target path exists as a directory: {rel_path!r}")

        staged_writes.append((target, norm_p, content))

    report_files: list[ImportedFile] = []

    for target, norm_p, content in staged_writes:
        data = content.encode("utf-8")
        num_bytes = len(data)
        num_lines = len(content.splitlines())
        digest = hashlib.sha256(data).hexdigest()

        report_files.append(ImportedFile(path=norm_p, bytes=num_bytes, lines=num_lines, sha256=digest))

    if not dry_run:
        for target, norm_p, content in staged_writes:
            data = content.encode("utf-8")
            target.parent.mkdir(parents=True, exist_ok=True)
            scratch = target.parent / f".tmp_{target.name}_{uuid.uuid4().hex}"
            try:
                scratch.write_bytes(data)
                os.replace(scratch, target)
            except OSError as exc:
                if scratch.exists():
                    scratch.unlink(missing_ok=True)
                raise ImportRefused(f"Failed writing file {norm_p!r}: {exc}") from exc

    return ImportReport(files=tuple(report_files))
