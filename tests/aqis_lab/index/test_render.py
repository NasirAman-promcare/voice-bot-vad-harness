"""Unit tests for tools.index.render (WO-1.0-03 step 4).

CAPABILITIES:
  none.
INPUTS AND OUTPUTS: pytest tests over in-memory ModuleFacts and Registry values; no I/O.
CONTRACTS: docs/process/CHANGE_CONTROL.md section 1; WO-1.0-03 B1-B5, B12 pins 6 and 12.
INVARIANTS:
  - No network, no sleeps, no randomness, no filesystem use.
  - No test depends on the real repository's contents.
NOT IN SCOPE:
  - Registry building (registry.py) and the command line (__main__.py); the acceptance test.
CHANGE LOG:
  2026-10-12 WP-1.0 FR-1.0-03 created.
  2026-10-12 WP-1.0 FR-1.0-03 fix 2: section() joins without a trailing newline; the test-fact
             builder renamed make_test_facts so pytest never collects it."""
from __future__ import annotations

from tools.index.registry import build_registry
from tools.index.render import (
    ALL_PATHS,
    GENERATED_LINE,
    REGISTRY_HEADER,
    render_all,
    render_map,
    render_registry,
    requirement_id,
)
from tools.index.scan import ModuleFacts, ParseError, Symbol

HEADER_TEMPLATE = (
    '"""{purpose}\n\nCAPABILITIES:\n{caps}\nINPUTS AND OUTPUTS: x in, y out.\n'
    'CONTRACTS: none.\nINVARIANTS:\n  - i.\nNOT IN SCOPE:\n  - n.\n'
    'CHANGE LOG:\n  {log}\n"""'
)


def make_facts(path: str, purpose: str = 'Module.', caps: list[str] | None = None,
               log: str = '2026-10-10 WP-9.1 FR-9.1-01 created.',
               symbols: tuple[Symbol, ...] = (), imports: tuple[str, ...] = (),
               tests: tuple[str, ...] = ()) -> ModuleFacts:
    caps_text = '\n'.join(f'  {cap}' for cap in caps) if caps else '  none.'
    return ModuleFacts(path=path,
                       docstring=HEADER_TEMPLATE.format(purpose=purpose, caps=caps_text, log=log),
                       symbols=symbols, imports=imports, tests=tests)


def alpha_facts(imports: tuple[str, ...] = ()) -> ModuleFacts:
    return make_facts(
        'aqis_lab/pkg/alpha.py', 'Alpha module.',
        ['CAP-SCR-001: doubles a number [tests: test_FR_9_1_01_alpha_works,',
         '    test_FR_9_1_02_alpha_listed_capability]'],
        symbols=(Symbol('alpha_fn', 'function', 'def alpha_fn(value: int) -> int:', 10),
                 Symbol('Alpha', 'class', 'class Alpha:', 14),
                 Symbol('Alpha.run', 'method', 'def run(self, value: int) -> int:', 15)),
        imports=imports)


def beta_facts(imports: tuple[str, ...] = ('aqis_lab/pkg/alpha.py',)) -> ModuleFacts:
    return make_facts('aqis_lab/pkg/beta.py', 'Beta module.',
                      ['CAP-SCR-002: adds one [tests: test_FR_9_2_01_beta_works]'],
                      log='2026-10-10 WO-9.2-01 created.',
                      symbols=(Symbol('beta_fn', 'function', 'def beta_fn(value: int) -> int:', 10),),
                      imports=imports)


def make_test_facts() -> tuple[ModuleFacts, ...]:
    """Facts for the five scratch test modules; not a test itself despite the data it holds."""
    return (
        make_facts('tests/aqis_lab/test_scr_alpha.py', 'Alpha tests.',
                   imports=('aqis_lab/pkg/alpha.py',),
                   tests=('test_FR_9_1_01_alpha_works',)),
        make_facts('tests/aqis_lab/test_scr_beta.py', 'Beta tests.',
                   imports=('aqis_lab/pkg/beta.py',),
                   tests=('test_FR_9_2_01_beta_works',)),
        make_facts('tests/aqis_lab/test_scr_other.py', 'Other tests.',
                   tests=('test_FR_9_1_02_alpha_listed_capability',
                          'test_NFR_9_1_01_unrelated')),
        make_facts('tests/aqis_lab/test_scr_pkg.py', 'Package tests.',
                   imports=('aqis_lab/pkg/__init__.py',),
                   tests=('test_AT_9_1_01_package_reexport',)),
        make_facts('tests/aqis_lab/test_scr_unrelated.py', 'Unrelated tests.',
                   tests=('test_DEBT_901_unrelated',)),
    )


def all_facts() -> tuple[ModuleFacts, ...]:
    pkg_init = make_facts('aqis_lab/pkg/__init__.py', 'Package.',
                          imports=('aqis_lab/pkg/alpha.py',))
    return (alpha_facts(), beta_facts(), pkg_init, *make_test_facts())


def section(text: str, heading: str) -> str:
    """The lines after the `## ` heading whose text is exactly `heading`, up to the next `## ` heading."""
    out: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.startswith('## '):
            if inside:
                break
            inside = line[3:].strip() == heading
            continue
        if inside:
            out.append(line)
    return '\n'.join(out)


def test_FR_1_0_03_the_five_files_start_with_the_generated_line() -> None:
    outputs = render_all(all_facts(), build_registry(all_facts(), None, None, None))
    assert sorted(outputs) == sorted(ALL_PATHS)
    for path, text in outputs.items():
        assert text.splitlines()[0] == GENERATED_LINE, path


def test_FR_1_0_03_map_groups_modules_by_package() -> None:
    text = render_map((make_facts('tools/zeta.py', 'Zeta.'),
                       make_facts('aqis_lab/one.py', 'One.'),
                       make_facts('aqis_lab/pkg/two.py', 'Two.')))
    packages = [line[3:] for line in text.splitlines() if line.startswith('## ')]
    assert packages == ['aqis_lab', 'aqis_lab/pkg', 'tools']
    assert text.index('`aqis_lab/one.py`') < text.index('`aqis_lab/pkg/two.py`') < text.index('`tools/zeta.py`')


def test_FR_1_0_03_map_line_holds_purpose_capabilities_wp_and_symbol_count() -> None:
    text = render_map((alpha_facts(), beta_facts()))
    alpha_line = next(line for line in text.splitlines() if line.startswith('- `aqis_lab/pkg/alpha.py`'))
    assert 'Alpha module.' in alpha_line
    assert 'CAP-SCR-001' in alpha_line
    assert 'WP-9.1' in alpha_line
    assert '3 public symbols' in alpha_line
    beta_line = next(line for line in text.splitlines() if line.startswith('- `aqis_lab/pkg/beta.py`'))
    assert 'WP-9.2' in beta_line, 'owning WP of a WO-9.2-01 change-log entry is WP-9.2'
    assert '1 public symbols' in beta_line


def test_FR_1_0_03_map_lists_a_module_without_docstring_as_no_header() -> None:
    text = render_map((ModuleFacts(path='tools/gamma.py', docstring=None), alpha_facts()))
    line = next(line for line in text.splitlines() if '`tools/gamma.py`' in line)
    assert line == '- `tools/gamma.py` — NO HEADER'


def test_FR_1_0_03_map_uses_no_change_log_when_the_header_lacks_a_token() -> None:
    text = render_map((make_facts('aqis_lab/nolog.py', 'No log.',
                                  ['CAP-NL-001: n [tests: t]'],
                                  log='2026-10-10 created without a token.'),))
    line = next(line for line in text.splitlines() if '`aqis_lab/nolog.py`' in line)
    assert 'NO CHANGE LOG' in line


def test_FR_1_0_03_symbols_lists_public_names_with_signature_and_path_line() -> None:
    text = render_all(all_facts(), build_registry(all_facts(), None, None, None))['docs/index/SYMBOLS.md']
    assert '- `alpha_fn` — def alpha_fn(value: int) -> int: — `aqis_lab/pkg/alpha.py:10`' in text
    assert '- `Alpha` — class Alpha: — `aqis_lab/pkg/alpha.py:14`' in text
    assert '- `Alpha.run` — def run(self, value: int) -> int: — `aqis_lab/pkg/alpha.py:15`' in text
    assert '- `beta_fn` — def beta_fn(value: int) -> int: — `aqis_lab/pkg/beta.py:10`' in text


def test_FR_1_0_03_symbols_excludes_private_names_and_marks_modules_without_symbols() -> None:
    text = render_all(all_facts(), build_registry(all_facts(), None, None, None))['docs/index/SYMBOLS.md']
    assert '_private_fn' not in text and '_hidden' not in text
    assert '- (no public symbols)' in section(text, '`tests/aqis_lab/test_scr_alpha.py`')


def test_FR_1_0_03_callers_lists_direct_importers_or_none() -> None:
    text = render_all(all_facts(), build_registry(all_facts(), None, None, None))['docs/index/CALLERS.md']
    alpha = section(text, '`aqis_lab/pkg/alpha.py`')
    assert '- `aqis_lab/pkg/beta.py`' in alpha
    assert '- `aqis_lab/pkg/__init__.py`' in alpha
    assert '- `tests/aqis_lab/test_scr_alpha.py`' in alpha
    beta_importers = [line for line in section(text, '`aqis_lab/pkg/beta.py`').splitlines()
                      if line.startswith('- ')]
    assert beta_importers == ['- `tests/aqis_lab/test_scr_beta.py`'], (
        'beta is imported by its test only: alpha never imports beta')
    assert '- (none)' in section(text, '`tests/aqis_lab/test_scr_unrelated.py`').splitlines()


def test_FR_1_0_03_testmap_maps_requirement_ids_to_nodes_and_imported_modules() -> None:
    text = render_all(all_facts(), build_registry(all_facts(), None, None, None))['docs/index/TESTMAP.md']
    fr = section(text, 'FR-9.1-01')
    assert '- `tests/aqis_lab/test_scr_alpha.py::test_FR_9_1_01_alpha_works`' in fr
    assert '- `aqis_lab/pkg/alpha.py`' in fr


def test_FR_1_0_03_testmap_reads_the_requirement_id_patterns() -> None:
    text = render_all(all_facts(), build_registry(all_facts(), None, None, None))['docs/index/TESTMAP.md']
    assert ('- `tests/aqis_lab/test_scr_other.py::test_NFR_9_1_01_unrelated`'
            in section(text, 'NFR-9.1-01'))
    assert ('- `tests/aqis_lab/test_scr_pkg.py::test_AT_9_1_01_package_reexport`'
            in section(text, 'AT-9.1-01'))
    assert ('- `tests/aqis_lab/test_scr_unrelated.py::test_DEBT_901_unrelated`'
            in section(text, 'DEBT-901'))
    assert requirement_id('test_FR_0_3_04_x') == 'FR-0.3-04'
    assert requirement_id('helper') is None
    assert requirement_id('test_SOMETHING') is None


def test_FR_1_0_03_testmap_drops_ids_that_match_no_test() -> None:
    text = render_all((alpha_facts(),), build_registry((alpha_facts(),), None, None, None))[
        'docs/index/TESTMAP.md']
    assert 'FR-9.1-01' not in text, 'test names only; capability lists never create IDs'


def test_FR_1_0_03_registry_renders_the_gate_columns_and_sorted_rows() -> None:
    registry = build_registry((beta_facts(), alpha_facts()), None, None, None)
    text = render_registry(registry)
    lines = text.splitlines()
    assert lines[0] == GENERATED_LINE
    assert REGISTRY_HEADER[0] in lines and REGISTRY_HEADER[1] in lines
    rows = [line for line in lines if line.startswith('| CAP-')]
    assert rows[0].startswith('| CAP-SCR-001 ') and rows[1].startswith('| CAP-SCR-002 ')
    assert rows[0] == ('| CAP-SCR-001 | `aqis_lab/pkg/alpha.py` | `alpha_fn`, `Alpha` | '
                       'doubles a number | `test_FR_9_1_01_alpha_works`, '
                       '`test_FR_9_1_02_alpha_listed_capability` | WP-9.1 | ACTIVE |')


def test_FR_1_0_03_parse_errors_keep_their_module_out_of_the_detail_files() -> None:
    broken = ModuleFacts(path='aqis_lab/broken.py', docstring=None,
                         parse_error=ParseError('aqis_lab/broken.py', 3, 'invalid syntax'))
    outputs = render_all((alpha_facts(), broken), build_registry((alpha_facts(),), None, None, None))
    assert 'aqis_lab/broken.py' in outputs['docs/index/MAP.md'], 'E1: NO HEADER keeps it visible'
    assert 'aqis_lab/broken.py' in outputs['docs/index/SYMBOLS.md']
    assert 'invalid syntax' not in outputs['docs/index/MAP.md'], 'rendering never reports errors'


def test_FR_1_0_03_rendering_is_byte_identical_for_reversed_inputs() -> None:
    facts = all_facts()
    registry = build_registry(facts, None, None, None)
    first = render_all(facts, registry)
    second = render_all(tuple(reversed(facts)), registry)
    assert first == second
    for path in ALL_PATHS:
        assert first[path] == render_all(facts, registry)[path]


def test_FR_1_0_03_a_symbol_at_line_one_of_a_docstring_less_module() -> None:
    fact = ModuleFacts(path='tools/gamma.py', docstring=None,
                       symbols=(Symbol('VALUE', 'constant', 'VALUE = 1', 1),))
    text = render_all((fact,), build_registry((), None, None, None))['docs/index/SYMBOLS.md']
    assert '`tools/gamma.py:1`' in text
