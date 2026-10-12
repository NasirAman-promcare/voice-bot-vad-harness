"""Unit tests for tools.index.registry (WO-1.0-03 step 3).

CAPABILITIES:
  none.
INPUTS AND OUTPUTS: pytest tests over in-memory ModuleFacts and scratch fragment directories.
CONTRACTS: docs/process/CHANGE_CONTROL.md sections 1-2; WO-1.0-03 B6, B7 and B12.
INVARIANTS:
  - No network, no sleeps, no randomness; nothing outside the scratch path is touched.
  - No test depends on the real repository's contents.
NOT IN SCOPE:
  - Rendering (render.py) and the command line (__main__.py); the read-only acceptance test.
CHANGE LOG:
  2026-10-12 WP-1.0 FR-1.0-03 created."""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.index.registry import (
    CapabilityRemoved,
    RegistryError,
    adopt_registry,
    build_registry,
    parse_record,
    parse_retirement,
)
from tools.index.scan import ModuleFacts, Symbol

HEADER_TEMPLATE = (
    '"""{purpose}\n\nCAPABILITIES:\n{caps}\nINPUTS AND OUTPUTS: x in, y out.\n'
    'CONTRACTS: none.\nINVARIANTS:\n  - i.\nNOT IN SCOPE:\n  - n.\n'
    'CHANGE LOG:\n  {log}\n"""'
)


def make_facts(path: str, purpose: str, caps: list[str], log: str,
               symbols: tuple[Symbol, ...] = ()) -> ModuleFacts:
    caps_text = '\n'.join(f'  {cap}' for cap in caps) if caps else '  none.'
    docstring = HEADER_TEMPLATE.format(purpose=purpose, caps=caps_text, log=log)
    return ModuleFacts(path=path, docstring=docstring, symbols=symbols)


def alpha_facts(caps: list[str] | None = None) -> ModuleFacts:
    return make_facts(
        'aqis_lab/pkg/alpha.py', 'Alpha module.',
        caps if caps is not None else [
            'CAP-SCR-001: doubles a number [tests: test_FR_9_1_01_alpha_works,',
            '    test_FR_9_1_02_alpha_listed_capability]'],
        '2026-10-10 WP-9.1 FR-9.1-01 created.',
        (Symbol('alpha_fn', 'function', 'def alpha_fn(value: int) -> int:', 10),
         Symbol('Alpha', 'class', 'class Alpha:', 14),
         Symbol('Alpha.run', 'method', 'def run(self, value: int) -> int:', 15)))


def beta_facts() -> ModuleFacts:
    return make_facts(
        'aqis_lab/pkg/beta.py', 'Beta module.',
        ['CAP-SCR-002: adds one [tests: test_FR_9_2_01_beta_works]'],
        '2026-10-10 WO-9.2-01 created.',
        (Symbol('beta_fn', 'function', 'def beta_fn(value: int) -> int:', 10),))


def write(root: Path, rel: str, text: str) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text, encoding='utf-8')


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path]:
    records = tmp_path / 'records.d'
    retired = tmp_path / 'retired.d'
    records.mkdir()
    retired.mkdir()
    return records, retired


def test_FR_1_0_03_header_capabilities_become_active_rows(dirs: tuple[Path, Path]) -> None:
    registry = build_registry((alpha_facts(), beta_facts()), dirs[1], dirs[0], None)
    assert [row.cap_id for row in registry.rows] == ['CAP-SCR-001', 'CAP-SCR-002']
    alpha = registry.row('CAP-SCR-001')
    assert alpha is not None
    assert alpha.cells[1] == '`aqis_lab/pkg/alpha.py`'
    assert alpha.cells[2] == '`alpha_fn`, `Alpha`'
    assert alpha.cells[3] == 'doubles a number'
    assert alpha.cells[4] == '`test_FR_9_1_01_alpha_works`, `test_FR_9_1_02_alpha_listed_capability`'
    assert alpha.cells[5] == 'WP-9.1'
    assert alpha.cells[6] == 'ACTIVE'


def test_FR_1_0_03_rows_are_sorted_by_capability_id(dirs: tuple[Path, Path]) -> None:
    facts = (make_facts('aqis_lab/z.py', 'Z.', ['CAP-SCR-010: zed [tests: test_z]'],
                        '2026-10-10 WP-9.1 FR-9.1-01 created.'),
             make_facts('aqis_lab/a.py', 'A.', ['CAP-SCR-002: ay [tests: test_a]'],
                        '2026-10-10 WP-9.1 FR-9.1-01 created.'))
    registry = build_registry(facts, dirs[1], dirs[0], None)
    assert [row.cap_id for row in registry.rows] == ['CAP-SCR-002', 'CAP-SCR-010']


def test_FR_1_0_03_a_capability_in_two_modules_is_an_error_naming_both(dirs: tuple[Path, Path]) -> None:
    clash = make_facts('aqis_lab/pkg/beta.py', 'Beta.',
                       ['CAP-SCR-001: also doubles [tests: test_other]'],
                       '2026-10-10 WP-9.1 FR-9.1-01 created.')
    with pytest.raises(RegistryError) as excinfo:
        build_registry((alpha_facts(), clash), dirs[1], dirs[0], None)
    message = str(excinfo.value)
    assert 'CAP-SCR-001' in message
    assert 'aqis_lab/pkg/alpha.py' in message and 'aqis_lab/pkg/beta.py' in message


def test_FR_1_0_03_pipes_in_cells_are_escaped_for_the_gate(dirs: tuple[Path, Path]) -> None:
    facts = (make_facts('aqis_lab/pkg/beta.py', 'Beta.',
                        ['CAP-SCR-002: mode a|b here [tests: test_FR_9_2_01_beta_works]'],
                        '2026-10-10 WP-9.2 FR-9.2-01 created.'),)
    row = build_registry(facts, dirs[1], dirs[0], None).row('CAP-SCR-002')
    assert row is not None
    assert row.cells[3] == 'mode a&#124;b here'


def test_FR_1_0_03_test_modules_are_never_registry_sources(dirs: tuple[Path, Path]) -> None:
    test_module = make_facts('tests/aqis_lab/test_scr_alpha.py', 'Tests.',
                             ['CAP-SCR-001: tests alpha [tests: test_FR_9_1_01_alpha_works]'],
                             '2026-10-10 WP-9.1 FR-9.1-01 created.')
    registry = build_registry((alpha_facts(), test_module), dirs[1], dirs[0], None)
    row = registry.row('CAP-SCR-001')
    assert row is not None
    assert row.cells[1] == '`aqis_lab/pkg/alpha.py`'


def test_FR_1_0_03_parse_errors_are_skipped_as_registry_sources(dirs: tuple[Path, Path]) -> None:
    from tools.index.scan import ParseError
    broken = ModuleFacts(path='aqis_lab/broken.py', docstring=None,
                         parse_error=ParseError('aqis_lab/broken.py', 3, 'invalid syntax'))
    registry = build_registry((alpha_facts(), broken), dirs[1], dirs[0], None)
    assert registry.row('CAP-SCR-001') is not None


def test_FR_1_0_03_removed_capability_without_retirement_raises(dirs: tuple[Path, Path]) -> None:
    previous = ('| Capability ID | Module | Functions | What it does | Tests | Introduced by | Status |\n'
                '| --- | --- | --- | --- | --- | --- | --- |\n'
                '| CAP-SCR-001 | `aqis_lab/pkg/alpha.py` | `alpha_fn` | Doubles | `test_a` | WP-9.1 | ACTIVE |\n')
    with pytest.raises(CapabilityRemoved, match='CAP-SCR-001'):
        build_registry((beta_facts(),), dirs[1], dirs[0], previous)


def test_FR_1_0_03_retired_capability_keeps_its_row_with_retired_status(dirs: tuple[Path, Path]) -> None:
    records, retired = dirs
    write(retired, 'CAP-SCR-001.md', 'CAP: CAP-SCR-001\nRetired in: WP-9.3\nAllowed by: DEC-9.3-01\n')
    previous = ('| Capability ID | Module | Functions | What it does | Tests | Introduced by | Status |\n'
                '| --- | --- | --- | --- | --- | --- | --- |\n'
                '| CAP-SCR-001 | `aqis_lab/pkg/alpha.py` | `alpha_fn` | Doubles | `test_a` | WP-9.1 | ACTIVE |\n'
                '| CAP-SCR-002 | `aqis_lab/pkg/beta.py` | `beta_fn` | Adds one | `test_b` | WP-9.2 | ACTIVE |\n')
    registry = build_registry((beta_facts(),), retired, records, previous)
    row = registry.row('CAP-SCR-001')
    assert row is not None
    assert row.cells[1] == '`aqis_lab/pkg/alpha.py`'
    assert row.cells[4] == '`test_a`'
    assert row.cells[6] == 'RETIRED in WP-9.3; allowed by DEC-9.3-01'
    assert registry.row('CAP-SCR-002').cells[6] == 'ACTIVE'


def test_FR_1_0_03_records_add_rows_verbatim(dirs: tuple[Path, Path]) -> None:
    records, retired = dirs
    write(records, 'CAP-DOC-901.md',
          'CAP: CAP-DOC-901\nModule: `docs/guide.md`\nFunctions: whole document\n'
          'What it does: Scratch guide\nTests: `test_FR_9_1_01_alpha_works`\n'
          'Introduced by: WP-9.1 FR-9.1-01\nStatus: ACTIVE\n')
    registry = build_registry((alpha_facts(),), retired, records, None)
    row = registry.row('CAP-DOC-901')
    assert row is not None
    assert row.cells == ('CAP-DOC-901', '`docs/guide.md`', 'whole document', 'Scratch guide',
                         '`test_FR_9_1_01_alpha_works`', 'WP-9.1 FR-9.1-01', 'ACTIVE')


def test_FR_1_0_03_record_filename_and_cap_line_must_agree(dirs: tuple[Path, Path]) -> None:
    records, retired = dirs
    write(records, 'CAP-DOC-901.md',
          'CAP: CAP-DOC-902\nModule: `docs/guide.md`\nFunctions: doc\nWhat it does: Guide\n'
          'Tests: none\nIntroduced by: WP-9.1\nStatus: ACTIVE\n')
    with pytest.raises(RegistryError, match='CAP-DOC-901'):
        build_registry((alpha_facts(),), retired, records, None)


def test_FR_1_0_03_record_and_header_sharing_an_id_is_an_error_naming_both(dirs: tuple[Path, Path]) -> None:
    records, retired = dirs
    write(records, 'CAP-SCR-001.md',
          'CAP: CAP-SCR-001\nModule: `docs/guide.md`\nFunctions: doc\nWhat it does: Guide\n'
          'Tests: none\nIntroduced by: WP-9.1\nStatus: ACTIVE\n')
    with pytest.raises(RegistryError) as excinfo:
        build_registry((alpha_facts(),), retired, records, None)
    message = str(excinfo.value)
    assert 'CAP-SCR-001' in message and 'aqis_lab/pkg/alpha.py' in message
    assert 'CAP-SCR-001.md' in message


def test_FR_1_0_03_removed_record_without_retirement_raises(dirs: tuple[Path, Path]) -> None:
    records, retired = dirs
    write(records, 'CAP-DOC-901.md',
          'CAP: CAP-DOC-901\nModule: `docs/guide.md`\nFunctions: doc\nWhat it does: Guide\n'
          'Tests: none\nIntroduced by: WP-9.1\nStatus: ACTIVE\n')
    previous_text = None
    registry = build_registry((alpha_facts(),), retired, records, previous_text)
    assert registry.row('CAP-DOC-901') is not None
    previous = ('| Capability ID | Module | Functions | What it does | Tests | Introduced by | Status |\n'
                '| --- | --- | --- | --- | --- | --- | --- |\n'
                '| CAP-DOC-901 | `docs/guide.md` | doc | Guide | none | WP-9.1 | ACTIVE |\n')
    (records / 'CAP-DOC-901.md').unlink()
    with pytest.raises(CapabilityRemoved, match='CAP-DOC-901'):
        build_registry((alpha_facts(),), retired, records, previous)


def test_FR_1_0_03_retirement_for_a_still_present_id_is_an_error(dirs: tuple[Path, Path]) -> None:
    records, retired = dirs
    write(retired, 'CAP-SCR-001.md', 'CAP: CAP-SCR-001\nRetired in: WP-9.3\nAllowed by: DEC-9.3-01\n')
    with pytest.raises(RegistryError, match='CAP-SCR-001'):
        build_registry((alpha_facts(),), retired, records, None)


def test_FR_1_0_03_retirement_for_an_unknown_id_is_an_error(dirs: tuple[Path, Path]) -> None:
    records, retired = dirs
    write(retired, 'CAP-GONE-001.md', 'CAP: CAP-GONE-001\nRetired in: WP-9.3\nAllowed by: DEC-9.3-01\n')
    with pytest.raises(RegistryError, match='CAP-GONE-001'):
        build_registry((alpha_facts(),), retired, records, None)


def test_FR_1_0_03_no_previous_registry_means_nothing_can_have_vanished(dirs: tuple[Path, Path]) -> None:
    registry = build_registry((), dirs[1], dirs[0], None)
    assert registry.rows == ()


def test_FR_1_0_03_owning_wp_falls_back_through_wo_and_no_change_log(dirs: tuple[Path, Path]) -> None:
    wo_only = make_facts('aqis_lab/wo.py', 'WO module.', ['CAP-WO-001: w [tests: t]'],
                         '2026-10-10 WO-9.2-01 created.')
    no_log = make_facts('aqis_lab/nolog.py', 'No log.', ['CAP-NL-001: n [tests: t]'],
                        '2026-10-10 created without a token.')
    registry = build_registry((wo_only, no_log), dirs[1], dirs[0], None)
    assert registry.row('CAP-WO-001').cells[5] == 'WP-9.2'
    assert registry.row('CAP-NL-001').cells[5] == 'NO CHANGE LOG'


def test_FR_1_0_03_functions_cell_uses_module_when_no_public_symbols(dirs: tuple[Path, Path]) -> None:
    bare = make_facts('aqis_lab/bare.py', 'Bare.', ['CAP-BARE-001: b [tests: t]'],
                      '2026-10-10 WP-9.1 FR-9.1-01 created.')
    row = build_registry((bare,), dirs[1], dirs[0], None).row('CAP-BARE-001')
    assert row is not None and row.cells[2] == 'module'


def test_FR_1_0_03_parse_record_requires_exactly_seven_labelled_lines() -> None:
    with pytest.raises(RegistryError, match='seven lines'):
        parse_record('CAP: CAP-X-001\nModule: m\n', 'records.d/CAP-X-001.md')
    cells = parse_record(
        'CAP: CAP-X-001\nModule: `m.py`\nFunctions: `f`\nWhat it does: x\n'
        'Tests: `t`\nIntroduced by: WP-1.0\nStatus: ACTIVE\n', 'records.d/CAP-X-001.md')
    assert cells[0] == 'CAP-X-001' and cells[6] == 'ACTIVE'


def test_FR_1_0_03_parse_retirement_reads_the_three_labels() -> None:
    cap_id, retired_in, allowed_by = parse_retirement(
        'CAP: CAP-X-001\nRetired in: WP-9.3\nAllowed by: DEC-9.3-01\n', 'retired.d/CAP-X-001.md')
    assert (cap_id, retired_in, allowed_by) == ('CAP-X-001', 'WP-9.3', 'DEC-9.3-01')
    with pytest.raises(RegistryError):
        parse_retirement('CAP: CAP-X-001\nRetired in: WP-9.3\n', 'retired.d/CAP-X-001.md')


LEGACY_HEAD = ('| Capability ID | Module | Functions | What it does | Tests | Introduced by | Status |\n'
               '| --- | --- | --- | --- | --- | --- | --- |\n')
LEGACY_ROWS = {
    'CAP-SCR-001': '| CAP-SCR-001 | `aqis_lab/pkg/alpha.py` | `alpha_fn` | Doubles | `test_FR_9_1_01_alpha_works` '
                   '| WP-9.1 FR-9.1-01 | ACTIVE |',
    'CAP-DOC-900': '| CAP-DOC-900 | `docs/guide.md` | sections a, b | Scratch guide | `test_a`, `test_b` '
                   '| WP-9.1 FR-9.1-01 | ACTIVE |',
    'CAP-OLD-001': '| CAP-OLD-001 | `aqis_lab/old.py` | `old_fn` | Old behaviour | `test_a` '
                   '| WP-9.0 FR-9.0-01 | RETIRED in WP-9.1 (APP-901) |',
}


def legacy_text(rows: list[str] | None = None) -> str:
    chosen = rows or list(LEGACY_ROWS)
    return LEGACY_HEAD + '\n'.join(LEGACY_ROWS[row] for row in chosen) + '\n'


def test_FR_1_0_03_adopt_registry_splits_rows_into_records_and_retirements(dirs: tuple[Path, Path]) -> None:
    planned = adopt_registry((alpha_facts(), beta_facts()), legacy_text(), dirs[0], dirs[1])
    assert set(planned) == {'docs/capabilities/records.d/CAP-DOC-900.md',
                            'docs/capabilities/retired.d/CAP-OLD-001.md'}
    assert planned['docs/capabilities/records.d/CAP-DOC-900.md'] == (
        'CAP: CAP-DOC-900\nModule: `docs/guide.md`\nFunctions: sections a, b\n'
        'What it does: Scratch guide\nTests: `test_a`, `test_b`\n'
        'Introduced by: WP-9.1 FR-9.1-01\nStatus: ACTIVE\n')
    assert planned['docs/capabilities/retired.d/CAP-OLD-001.md'] == (
        'CAP: CAP-OLD-001\nRetired in: WP-9.1\nAllowed by: RETIRED in WP-9.1 (APP-901)\n')


def test_FR_1_0_03_adoption_skips_rows_a_header_names(dirs: tuple[Path, Path]) -> None:
    planned = adopt_registry((alpha_facts(),), legacy_text(['CAP-SCR-001']), dirs[0], dirs[1])
    assert planned == {}


def test_FR_1_0_03_adoption_refuses_a_retired_row_without_a_wp(dirs: tuple[Path, Path]) -> None:
    row = LEGACY_ROWS['CAP-OLD-001'].replace('RETIRED in WP-9.1 (APP-901)', 'RETIRED')
    text = LEGACY_HEAD + row + '\n'
    with pytest.raises(RegistryError, match='CAP-OLD-001'):
        adopt_registry((alpha_facts(),), text, dirs[0], dirs[1])


def test_FR_1_0_03_adoption_checks_everything_before_writing_anything(dirs: tuple[Path, Path]) -> None:
    bad = LEGACY_ROWS['CAP-OLD-001'].replace('RETIRED in WP-9.1 (APP-901)', 'RETIRED')
    text = LEGACY_HEAD + LEGACY_ROWS['CAP-DOC-900'] + '\n' + bad + '\n'
    with pytest.raises(RegistryError, match='CAP-OLD-001'):
        adopt_registry((alpha_facts(), beta_facts()), text, dirs[0], dirs[1])
    assert list(dirs[0].iterdir()) == [] and list(dirs[1].iterdir()) == []


def test_FR_1_0_03_adoption_is_idempotent(dirs: tuple[Path, Path]) -> None:
    facts = (alpha_facts(), beta_facts())
    planned = adopt_registry(facts, legacy_text(), dirs[0], dirs[1])
    for rel, text in planned.items():
        name = rel.rsplit('/', 1)[1]
        target = dirs[0] / name if 'records.d' in rel else dirs[1] / name
        target.write_text(text, encoding='utf-8')
    again = adopt_registry(facts, legacy_text(), dirs[0], dirs[1])
    assert again == {}


def test_FR_1_0_03_existing_record_with_different_cells_is_an_error(dirs: tuple[Path, Path]) -> None:
    records, retired = dirs
    write(records, 'CAP-DOC-900.md',
          'CAP: CAP-DOC-900\nModule: `docs/guide.md`\nFunctions: changed\nWhat it does: Scratch guide\n'
          'Tests: `test_a`, `test_b`\nIntroduced by: WP-9.1 FR-9.1-01\nStatus: ACTIVE\n')
    with pytest.raises(RegistryError, match='CAP-DOC-900'):
        adopt_registry((alpha_facts(), beta_facts()), legacy_text(), records, retired)


def test_FR_1_0_03_previous_rows_unescapes_pipe_entities(dirs: tuple[Path, Path]) -> None:
    previous = ('| Capability ID | Module | Functions | What it does | Tests | Introduced by | Status |\n'
                '| --- | --- | --- | --- | --- | --- | --- |\n'
                '| CAP-SCR-001 | `aqis_lab/pkg/alpha.py` | `alpha_fn` | mode a&#124;b | `test_a` | WP-9.1 | ACTIVE |\n')
    write(dirs[1], 'CAP-SCR-001.md', 'CAP: CAP-SCR-001\nRetired in: WP-9.3\nAllowed by: DEC-9.3-01\n')
    registry = build_registry((), dirs[1], dirs[0], previous)
    row = registry.row('CAP-SCR-001')
    assert row is not None and row.cells[3] == 'mode a&#124;b'
    assert row.cells[6] == 'RETIRED in WP-9.3; allowed by DEC-9.3-01'
