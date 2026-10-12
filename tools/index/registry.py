"""Build the capability registry from module headers, capability records and retirement records.

CAPABILITIES:
  CAP-INDEX-003: build_registry() merges header capabilities (aqis_lab/, tools/, kit-staging/ only),
  seven-line records under docs/capabilities/records.d/ and retirements under
  docs/capabilities/retired.d/ into one Registry, comparing against the previous committed
  registry so a capability that vanishes without a retirement record raises CapabilityRemoved;
  adopt_registry() migrates a hand-written registry into records and retirements
  [tests: test_FR_1_0_03_header_capabilities_become_active_rows,
  test_FR_1_0_03_rows_are_sorted_by_capability_id,
  test_FR_1_0_03_a_capability_in_two_modules_is_an_error_naming_both,
  test_FR_1_0_03_pipes_in_cells_are_escaped_for_the_gate,
  test_FR_1_0_03_test_modules_are_never_registry_sources,
  test_FR_1_0_03_removed_capability_without_retirement_raises,
  test_FR_1_0_03_retired_capability_keeps_its_row_with_retired_status,
  test_FR_1_0_03_records_add_rows_verbatim,
  test_FR_1_0_03_record_filename_and_cap_line_must_agree,
  test_FR_1_0_03_record_and_header_sharing_an_id_is_an_error_naming_both,
  test_FR_1_0_03_removed_record_without_retirement_raises,
  test_FR_1_0_03_retirement_for_a_still_present_id_is_an_error,
  test_FR_1_0_03_retirement_for_an_unknown_id_is_an_error,
  test_FR_1_0_03_no_previous_registry_means_nothing_can_have_vanished,
  test_FR_1_0_03_owning_wp_falls_back_through_wo_and_no_change_log,
  test_FR_1_0_03_functions_cell_uses_module_when_no_public_symbols,
  test_FR_1_0_03_adopt_registry_splits_rows_into_records_and_retirements,
  test_FR_1_0_03_adoption_skips_rows_a_header_names,
  test_FR_1_0_03_adoption_refuses_a_retired_row_without_a_wp,
  test_FR_1_0_03_adoption_checks_everything_before_writing_anything,
  test_FR_1_0_03_adoption_is_idempotent,
  test_FR_1_0_03_existing_record_with_different_cells_is_an_error]
INPUTS AND OUTPUTS: ModuleFacts from scan, the records.d/retired.d directories and the previous
  registry text in; a Registry of sorted RegistryRow values out. adopt_registry() returns the
  record and retirement texts to write; the caller writes them.
CONTRACTS: docs/process/CHANGE_CONTROL.md sections 1-2; WO-1.0-03 B6, B7 and B12 pins 3, 5, 6, 7, 8, 10;
  registry columns per tools.audit.gate.
INVARIANTS:
  - Deterministic: sorted iteration everywhere; no clock, locale or environment reads.
  - build_registry() raises RegistryError subclasses; it never writes and never drops a capability silently.
NOT IN SCOPE:
  - Scanning (scan.py), rendering the markdown (render.py), the command line (__main__.py).
CHANGE LOG:
  2026-10-12 WP-1.0 FR-1.0-03 created."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from tools.index.headers import Capability, Header, parse_header
from tools.index.scan import ModuleFacts, is_registry_source

__all__ = [
    'CapabilityRemoved',
    'Registry',
    'RegistryError',
    'RegistryRow',
    'RETIREMENT_LABELS',
    'build_registry',
    'adopt_registry',
    'escape_cell',
    'parse_record',
    'parse_retirement',
    'previous_rows',
]

RECORD_LABELS = ('CAP', 'Module', 'Functions', 'What it does', 'Tests', 'Introduced by', 'Status')
RETIREMENT_LABELS = ('CAP', 'Retired in', 'Allowed by')
REGISTRY_REL = 'docs/capabilities/REGISTRY.md'
RECORDS_REL = 'docs/capabilities/records.d'
RETIRED_REL = 'docs/capabilities/retired.d'

_CAP_ID = re.compile(r'^CAP-[A-Z0-9-]+$')
_CAP_START = re.compile(r'^\s+(CAP-[A-Z0-9-]+):\s*(.*)$')
_WP_TOKEN = re.compile(r'WP-\d+\.\d+')
_WO_TOKEN = re.compile(r'WO-(\d+\.\d+)-\d+')
_TESTS_BRACKET = re.compile(r'\[tests:[^\]]*\]')
_SECTION_HEAD = re.compile(r'^[A-Z][A-Z ]+:')


class RegistryError(Exception):
    """The registry cannot be built or adopted: capabilities duplicated, mismatched or retired wrongly."""


class CapabilityRemoved(RegistryError):
    """Capabilities present in the previous committed registry vanished without a retirement record."""

    def __init__(self, cap_ids: list[str]) -> None:
        self.cap_ids = tuple(sorted(cap_ids))
        joined = ', '.join(self.cap_ids)
        super().__init__(
            f'capabilities vanished without a retirement record: {joined}; '
            'restore the header or record, or add docs/capabilities/retired.d/<CAP-ID>.md')


@dataclass(frozen=True)
class RegistryRow:
    """One registry row: the seven cells exactly as they will be rendered (pipe-escaped)."""
    cells: tuple[str, str, str, str, str, str, str]

    @property
    def cap_id(self) -> str:
        return self.cells[0]


@dataclass(frozen=True)
class Registry:
    """The full registry: rows sorted by capability ID."""
    rows: tuple[RegistryRow, ...]

    def row(self, cap_id: str) -> RegistryRow | None:
        for row in self.rows:
            if row.cap_id == cap_id:
                return row
        return None


def escape_cell(text: str) -> str:
    """Escape a table cell so the gate's column split stays exact (B12 pin 6)."""
    return text.replace('|', '&#124;')


def parse_record(text: str, path: str) -> tuple[str, ...]:
    """Seven cells from a records.d file: exactly seven labelled lines, cells verbatim (B12 pin 7)."""
    lines = text.splitlines()
    if len(lines) != 7:
        raise RegistryError(f'{path}: a capability record is exactly seven lines, found {len(lines)}')
    cells = []
    for label, line in zip(RECORD_LABELS, lines):
        prefix = f'{label}: '
        if not line.startswith(prefix):
            raise RegistryError(f'{path}: expected a line starting {prefix!r}, found {line!r}')
        cells.append(line[len(prefix):])
    if not _CAP_ID.match(cells[0]):
        raise RegistryError(f'{path}: CAP line does not name a capability ID: {cells[0]!r}')
    return tuple(cells)


def parse_retirement(text: str, path: str) -> tuple[str, str, str]:
    """(cap_id, retired_in, allowed_by) from a retired.d file: lines CAP:, Retired in:, Allowed by: (B6)."""
    values = []
    for label, line in zip(RETIREMENT_LABELS, text.splitlines()):
        prefix = f'{label}: '
        if not line.startswith(prefix):
            raise RegistryError(f'{path}: expected a line starting {prefix!r}, found {line!r}')
        values.append(line[len(prefix):])
    if len(values) != 3:
        raise RegistryError(f'{path}: a retirement record is exactly three lines')
    if not _CAP_ID.match(values[0]):
        raise RegistryError(f'{path}: CAP line does not name a capability ID: {values[0]!r}')
    if not values[1] or not values[2]:
        raise RegistryError(f'{path}: Retired in and Allowed by must both be filled')
    return values[0], values[1], values[2]


def previous_rows(text: str | None) -> dict[str, tuple[str, ...]]:
    """{cap_id: seven cells, unescaped} parsed from the previous committed registry via the gate."""
    if text is None or not text.strip():
        return {}
    from tools.audit.gate import parse_registry  # deferred: keep module import side-effect light
    rows, problems = parse_registry(text)
    if problems:
        detail = '; '.join(f'line {line}: {problem}' for line, problem in problems)
        raise RegistryError(f'previous registry is malformed: {detail}')
    return {cells[0]: tuple(cells) for _, cells in rows}


def _unescape(text: str) -> str:
    return text.replace('&#124;', '|')


def _read_fragment(folder: Path | None, stem_pattern: re.Pattern[str]) -> dict[str, tuple[Path, str]]:
    """{stem: (path, text)} for the *.md fragments of a directory; {} when absent. Sorted for determinism."""
    if folder is None or not folder.is_dir():
        return {}
    found = {}
    for path in sorted(folder.glob('*.md')):
        if not stem_pattern.match(path.stem):
            raise RegistryError(f'{path.as_posix()}: file name is not a capability ID')
        found[path.stem] = (path, path.read_text(encoding='utf-8'))
    return found


def _owning_wp(header: Header) -> str:
    """The owning WP per B12 pin 5: first WP token of the first change-log entry, else its WO, else a marker."""
    if not header.change_log:
        return 'NO CHANGE LOG'
    first = header.change_log[0]
    wp = _WP_TOKEN.search(first)
    if wp:
        return wp.group(0)
    wo = _WO_TOKEN.search(first)
    if wo:
        return f'WP-{wo.group(1)}'
    return 'NO CHANGE LOG'


def _functions_cell(facts: ModuleFacts) -> str:
    """Public top-level functions and classes in source order, each in backticks; `module` when none."""
    names = [symbol.name for symbol in facts.symbols if symbol.kind in ('function', 'class')]
    if not names:
        return 'module'
    return ', '.join(f'`{name}`' for name in names)


def _tests_cell(tests: tuple[str, ...]) -> str:
    return ', '.join(f'`{name}`' for name in tests)


def _header_row(facts: ModuleFacts, capability: Capability, header: Header) -> RegistryRow:
    return RegistryRow((
        capability.cap_id,
        f'`{facts.path}`',
        _functions_cell(facts),
        escape_cell(capability.description),
        _tests_cell(capability.tests),
        _owning_wp(header),
        'ACTIVE',
    ))


def _record_row(cells: tuple[str, ...], path: str) -> RegistryRow:
    return RegistryRow(tuple(escape_cell(cell) if '|' in cell else cell for cell in cells))


def _collect_header_rows(facts: tuple[ModuleFacts, ...]) -> dict[str, tuple[ModuleFacts, Capability, Header]]:
    """{cap_id: (facts, capability, header)} for registry-source modules; E3 raises naming both modules."""
    found: dict[str, tuple[ModuleFacts, Capability, Header]] = {}
    for fact in facts:
        if not is_registry_source(fact) or fact.parse_error is not None:
            continue
        header = parse_header(fact.docstring)
        for capability in header.capabilities:
            if capability.cap_id in found:
                first = found[capability.cap_id][0]
                raise RegistryError(
                    f'{capability.cap_id} is listed in two modules: {first.path} and {fact.path}')
            found[capability.cap_id] = (fact, capability, header)
    return found


def build_registry(
    facts: tuple[ModuleFacts, ...],
    retired_dir: Path | None,
    records_dir: Path | None,
    previous_registry_text: str | None,
) -> Registry:
    """Merge header capabilities, records and retirements into the registry.

Raises RegistryError for duplicates, mismatched records or bad retirements, and
CapabilityRemoved for capabilities of the previous registry now missing everywhere."""
    headers = _collect_header_rows(facts)
    previous = previous_rows(previous_registry_text)

    records: dict[str, tuple[Path, tuple[str, ...]]] = {}
    for stem, (path, text) in _read_fragment(records_dir, _CAP_ID).items():
        cells = parse_record(text, path.as_posix())
        if cells[0] != stem:
            raise RegistryError(
                f'{path.as_posix()}: file name {stem} and CAP line {cells[0]} differ')
        records[cells[0]] = (path, cells)

    retirements: dict[str, tuple[Path, str, str]] = {}
    for stem, (path, text) in _read_fragment(retired_dir, _CAP_ID).items():
        cap_id, retired_in, allowed_by = parse_retirement(text, path.as_posix())
        if cap_id != stem:
            raise RegistryError(
                f'{path.as_posix()}: file name {stem} and CAP line {cap_id} differ')
        retirements[cap_id] = (path, retired_in, allowed_by)

    for cap_id in sorted(set(headers) & set(records)):
        record_path = records[cap_id][0]
        raise RegistryError(
            f'{cap_id} is named by both header module {headers[cap_id][0].path} and '
            f'record {record_path.as_posix()}')
    for cap_id in sorted(set(retirements) & (set(headers) | set(records))):
        where = headers[cap_id][0].path if cap_id in headers else records[cap_id][0].as_posix()
        raise RegistryError(
            f'{cap_id} has a retirement record at {retirements[cap_id][0].as_posix()} '
            f'but still appears in {where}')

    rows: dict[str, RegistryRow] = {}
    for cap_id, (fact, capability, header) in headers.items():
        rows[cap_id] = _header_row(fact, capability, header)
    for cap_id, (path, cells) in records.items():
        rows[cap_id] = _record_row(cells, path.as_posix())

    for cap_id in sorted(retirements):
        if cap_id not in previous:
            raise RegistryError(
                f'{cap_id} has a retirement record but the previous registry has no row for it')
        path, retired_in, allowed_by = retirements[cap_id]
        old = previous[cap_id]
        rows[cap_id] = RegistryRow((
            cap_id, old[1], old[2], old[3], old[4], old[5],
            escape_cell(f'RETIRED in {retired_in}; allowed by {allowed_by}'),
        ))

    vanished = sorted(set(previous) - set(rows))
    if vanished:
        raise CapabilityRemoved(vanished)
    return Registry(tuple(rows[cap_id] for cap_id in sorted(rows)))


def _parse_row_line(line: str) -> list[str] | None:
    """Cells of one registry table line (stripped), or None when the line is not a table row."""
    stripped = line.strip()
    if not stripped.startswith('|') or not stripped.endswith('|'):
        return None
    return [cell.strip() for cell in stripped[1:-1].split('|')]


def adopt_registry(
    facts: tuple[ModuleFacts, ...],
    registry_text: str,
    records_dir: Path | None,
    retired_dir: Path | None,
) -> dict[str, str]:
    """Fragments to create from a hand-written registry: {repo-relative path: text} (B12 pin 10).

Header-named rows are left to their header. Rows whose Status contains `retired` (any case)
become retirement records; every other row becomes a capability record verbatim. Existing
fragments are never rewritten; one whose cells differ is an error. Every check runs first:
on any error the returned dict is never produced and the caller writes nothing."""
    headers = _collect_header_rows(facts)
    rows, problems = parse_registry(registry_text) if False else (None, None)
    # parse with the gate, as pin 10 requires
    from tools.audit.gate import parse_registry
    parsed, problems = parse_registry(registry_text)
    if problems:
        detail = '; '.join(f'line {line}: {problem}' for line, problem in problems)
        raise RegistryError(f'cannot adopt a malformed registry: {detail}')

    existing_records: dict[str, tuple[Path, tuple[str, ...]]] = {}
    for stem, (path, text) in _read_fragment(records_dir, _CAP_ID).items():
        existing_records[stem] = (path, parse_record(text, path.as_posix()))
    existing_retired = set(_read_fragment(retired_dir, _CAP_ID))

    planned: dict[str, str] = {}
    for _, cells in parsed:
        cap_id = _unescape(cells[0])
        if cap_id in headers:
            continue
        if cap_id in existing_records or cap_id in existing_retired:
            continue
        status = cells[6]
        if 'retired' in status.lower():
            wp = _WP_TOKEN.search(_unescape(status))
            if wp is None:
                raise RegistryError(
                    f'{cap_id}: retired row has no WP token in its Status cell: {_unescape(status)!r}')
            planned[f'{RETIRED_REL}/{cap_id}.md'] = (
                f'CAP: {cap_id}\nRetired in: {wp.group(0)}\nAllowed by: {_unescape(status)}\n')
        else:
            body = ''.join(f'{label}: {_unescape(cell)}\n' for label, cell in zip(RECORD_LABELS, cells))
            planned[f'{RECORDS_REL}/{cap_id}.md'] = body

    for cap_id, (path, cells) in existing_records.items():
        for _, row_cells in parsed:
            if _unescape(row_cells[0]) == cap_id:
                if tuple(_unescape(cell) for cell in row_cells) != cells:
                    raise RegistryError(
                        f'{path.as_posix()}: existing record cells differ from the registry row for {cap_id}')
                break
    return planned
