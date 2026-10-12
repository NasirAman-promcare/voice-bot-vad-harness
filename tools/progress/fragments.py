"""Parse progress fragment files into records, one item per file.

CAPABILITIES:
  CAP-PROGRESS-002: load all fragment kinds from their folders with source paths
    [tests: test_B1_status_fragment_fields, test_B1_blocker_labelled_lines_and_free_text,
    test_B1_decision_cannot_do_answers, test_B1_debt_fragment_fields, test_B1_ledger_fragment_fields,
    test_B1_unknown_fragment_file_is_ignored, test_B1_missing_folders_are_empty]
  CAP-PROGRESS-003: report parse problems as FragmentError with path and line
    [tests: test_E2_windows_line_endings_and_trailing_space_after_key,
    test_E6_parse_error_names_path_and_line, test_E6_key_without_value_is_a_parse_error,
    test_E6_labelled_line_before_marker_is_a_parse_error]
INPUTS AND OUTPUTS: files under docs/progress/*.d and docs/outsourcing/ledger.d; returns Fragments.
CONTRACTS: fragment formats v1 (docs/process/templates/FRAGMENTS.md, BLOCKER.md, DECISION.md).
INVARIANTS:
  - Parsing never writes to the repository.
  - Iteration over fragment directories is sorted.
  - A parse error is never treated as an empty fragment.
NOT IN SCOPE:
  - Lint rules, rendering, ID allocation and migration (separate modules).
CHANGE LOG:
  2026-10-12 WP-1.0 WO-1.0-04 step 1 created.
  2026-10-12 WP-1.0 WO-1.0-04 (Claude, FIX-WO04-final): a blocker's or decision's ID comes from its `# <ID> — <title>` heading; template labels after the first block are read (B2 clarification).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "FragmentError",
    "StatusFragment",
    "BlockerFragment",
    "DebtFragment",
    "DecisionFragment",
    "LedgerFragment",
    "Fragments",
    "load_all",
]

STATUS_DIR = Path("docs/progress/status.d")
BLOCKER_DIR = Path("docs/progress/blockers.d")
DEBT_DIR = Path("docs/progress/debt.d")
DECISION_DIR = Path("docs/progress/decisions.d")
LEDGER_DIR = Path("docs/outsourcing/ledger.d")

_FRAGMENT_SUFFIX = ".md"


class FragmentError(Exception):
    """A fragment file could not be parsed. The message names path and line."""

    def __init__(self, path: Path, line: int, reason: str) -> None:
        self.path = path
        self.line = line
        self.reason = reason
        super().__init__(f"{path}:{line}: {reason}")


@dataclass(frozen=True)
class StatusFragment:
    path: Path
    fields: dict[str, str]
    free_text: str


@dataclass(frozen=True)
class BlockerFragment:
    path: Path
    fields: dict[str, str]
    steps: tuple[str, ...]
    free_text: str


@dataclass(frozen=True)
class DebtFragment:
    path: Path
    fields: dict[str, str]
    free_text: str


@dataclass(frozen=True)
class DecisionFragment:
    path: Path
    fields: dict[str, str]
    options: tuple[str, ...]
    cannot_do: tuple[tuple[str, str], ...]
    free_text: str


@dataclass(frozen=True)
class LedgerFragment:
    path: Path
    fields: dict[str, str]
    free_text: str


@dataclass(frozen=True)
class Fragments:
    status: tuple[StatusFragment, ...]
    blockers: tuple[BlockerFragment, ...]
    debt: tuple[DebtFragment, ...]
    decisions: tuple[DecisionFragment, ...]
    ledger: tuple[LedgerFragment, ...]


def _split_lines(raw: str) -> list[str]:
    # E2: accept Windows line endings and a trailing space after a key.
    return [line.replace("\r\n", "\n").replace("\r", "\n") for line in raw.split("\n")]


def _parse_key_value(path: Path, lines: list[str], start: int) -> tuple[dict[str, str], int]:
    """Read `Key: value` lines until the first non-matching line; return fields and next index."""
    fields: dict[str, str] = {}
    index = start
    while index < len(lines):
        line = lines[index]
        if line.strip() == "":
            break
        if ":" not in line:
            break
        key, _, value = line.partition(":")
        key = key.strip()
        if not key:
            raise FragmentError(path, index + 1, "empty key in a labelled line")
        fields[key] = value.strip()
        index += 1
    return fields, index


def _free_text(path: Path, lines: list[str], start: int) -> str:
    if start > len(lines):
        raise FragmentError(path, len(lines) or 1, "fragment ends inside its labelled lines")
    return "\n".join(lines[start:]).strip("\n")


def _parse_numbered_block(lines: list[str], start: int) -> tuple[tuple[str, ...], int]:
    """Parse `1. ...` to `n. ...` lines from start; return entries and next index."""
    items: list[str] = []
    index = start
    expected = 1
    while index < len(lines):
        line = lines[index].strip()
        prefix = f"{expected}."
        if not line.startswith(prefix):
            break
        items.append(line[len(prefix):].strip())
        expected += 1
        index += 1
    return tuple(items), index


def _find_label(lines: list[str], label: str) -> int | None:
    for index, line in enumerate(lines):
        if line.strip() == label:
            return index
    return None


def _heading_id(lines: list[str]) -> str | None:
    """The `<ID>` of a first line `# <ID> — <title>` (BLOCKER.md, DECISION.md), or None."""
    if not lines or not lines[0].startswith("# "):
        return None
    head = lines[0][2:].split(" — ", 1)[0].strip()
    return head or None


_BLOCKER_LABELS = ("What I need", "Why", "What I tried", "Options", "Exact steps", "Meanwhile", "Owner answer")
_DECISION_LABELS = ("Spec basis", "Question", "Options", "Choice", "Why", "Reversal")


def _template_fields(fields: dict[str, str], lines: list[str], start: int, labels: tuple[str, ...]) -> None:
    """Template labels after the first block (B2): the value on the line, else the lines up to the next label."""
    if fields.get("Legacy") == "yes":
        return
    found: list[tuple[str, int]] = [(line.partition(":")[0].strip(), i) for i, line in enumerate(lines)
                                    if i >= start and line.partition(":")[0].strip() in labels and ":" in line]
    for n, (label, i) in enumerate(found):
        end = found[n + 1][1] if n + 1 < len(found) else len(lines)
        value = lines[i].partition(":")[2].strip() or " ".join(x.strip() for x in lines[i + 1:end] if x.strip())
        fields.setdefault(label, value)


def _parse_status(path: Path, raw: str) -> StatusFragment:
    lines = _split_lines(raw)
    fields, index = _parse_key_value(path, lines, 0)
    return StatusFragment(path=path, fields=fields, free_text=_free_text(path, lines, index))


def _parse_debt(path: Path, raw: str) -> DebtFragment:
    lines = _split_lines(raw)
    fields, index = _parse_key_value(path, lines, 0)
    return DebtFragment(path=path, fields=fields, free_text=_free_text(path, lines, index))


def _parse_ledger(path: Path, raw: str) -> LedgerFragment:
    lines = _split_lines(raw)
    fields, index = _parse_key_value(path, lines, 0)
    return LedgerFragment(path=path, fields=fields, free_text=_free_text(path, lines, index))


def _parse_blocker(path: Path, raw: str) -> BlockerFragment:
    lines = _split_lines(raw)
    start = 1 if lines and lines[0].startswith("# ") else 0
    fields, index = _parse_key_value(path, lines, start)
    if "Status" not in fields:
        raise FragmentError(path, start + 1, "blocker is missing its Status line")
    if "ID" not in fields and _heading_id(lines):
        fields["ID"] = _heading_id(lines)
    _template_fields(fields, lines, index, _BLOCKER_LABELS)
    steps_label = _find_label(lines, "Exact steps:")
    steps: tuple[str, ...] = ()
    if steps_label is not None:
        steps, _ = _parse_numbered_block(lines, steps_label + 1)
    return BlockerFragment(path=path, fields=fields, steps=steps, free_text=_free_text(path, lines, index))


def _parse_decision(path: Path, raw: str) -> DecisionFragment:
    lines = _split_lines(raw)
    start = 1 if lines and lines[0].startswith("# ") else 0
    fields, index = _parse_key_value(path, lines, start)
    if "Status" not in fields:
        raise FragmentError(path, start + 1, "decision is missing its Status line")
    if "ID" not in fields and _heading_id(lines):
        fields["ID"] = _heading_id(lines)
    _template_fields(fields, lines, index, _DECISION_LABELS)
    options: tuple[str, ...] = ()
    options_label = _find_label(lines, "Options:")
    if options_label is not None:
        options, _ = _parse_numbered_block(lines, options_label + 1)
    cannot_do: list[tuple[str, str]] = []
    cannot_do_label = _find_label(lines, 'Cannot-do check (all must be "no"):')
    if cannot_do_label is not None:
        for line in lines[cannot_do_label + 1:]:
            stripped = line.strip()
            if not stripped.startswith("- "):
                break
            body = stripped[2:]
            if ":" not in body:
                raise FragmentError(path, lines.index(line) + 1, "cannot-do line is not `question: answer`")
            question, _, answer = body.partition(":")
            cannot_do.append((question.strip(), answer.strip()))
    return DecisionFragment(path=path, fields=fields, options=options, cannot_do=tuple(cannot_do),
                            free_text=_free_text(path, lines, index))


def _load_folder(repo_root: Path, folder: Path, parse) -> tuple:
    base = repo_root / folder
    if not base.is_dir():
        return ()
    records = []
    for path in sorted(base.rglob(f"*{_FRAGMENT_SUFFIX}")):
        raw = path.read_text(encoding="utf-8")
        records.append(parse(path, raw))
    return tuple(records)


def load_all(repo_root: Path) -> Fragments:
    """Load every fragment under the five fragment folders of repo_root."""
    return Fragments(
        status=_load_folder(repo_root, STATUS_DIR, _parse_status),
        blockers=_load_folder(repo_root, BLOCKER_DIR, _parse_blocker),
        debt=_load_folder(repo_root, DEBT_DIR, _parse_debt),
        decisions=_load_folder(repo_root, DECISION_DIR, _parse_decision),
        ledger=_load_folder(repo_root, LEDGER_DIR, _parse_ledger),
    )
