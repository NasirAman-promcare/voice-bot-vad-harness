"""Unit tests for tools.index.scan (WO-1.0-03 step 2).

CAPABILITIES:
  none.
INPUTS AND OUTPUTS: pytest tests over scratch repositories built under pytest's scratch path.
CONTRACTS: docs/process/CHANGE_CONTROL.md section 1.
INVARIANTS:
  - No network, no sleeps, no randomness; nothing outside the scratch path is touched.
  - No test depends on the real repository's contents.
NOT IN SCOPE:
  - Registry, rendering and impact (later steps); the read-only acceptance test.
CHANGE LOG:
  2026-10-12 WP-1.0 FR-1.0-03 created."""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.index.scan import ModuleFacts, is_registry_source, scan

DOC = '"""Docstring for {name}.\n\nCAPABILITIES:\n  none.\nINPUTS AND OUTPUTS: x.\nCONTRACTS: none.\n' \
      'INVARIANTS:\n  - i.\nNOT IN SCOPE:\n  - n.\nCHANGE LOG:\n  2026-10-10 WP-9.1 FR-9.1-01 created.\n"""\n'


def write(root: Path, rel: str, text: str) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text, encoding='utf-8')


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / 'repo'
    root.mkdir()
    return root


def facts_by_path(facts: tuple[ModuleFacts, ...]) -> dict[str, ModuleFacts]:
    return {fact.path: fact for fact in facts}


def test_FR_1_0_03_walks_the_three_trees_and_skips_fixtures(repo: Path) -> None:
    write(repo, 'aqis_lab/pkg/alpha.py', DOC.format(name='alpha'))
    write(repo, 'tools/beta.py', DOC.format(name='beta'))
    write(repo, 'tests/aqis_lab/test_gamma.py', DOC.format(name='gamma'))
    write(repo, 'tests/aqis_lab/fixtures/gate/data.py', 'def broken(:\n')
    write(repo, 'docs/guide.py', DOC.format(name='guide'))
    write(repo, 'aqis_lab/__pycache__/cached.py', DOC.format(name='cached'))
    write(repo, '.hidden/secret.py', DOC.format(name='secret'))
    paths = [fact.path for fact in scan(repo)]
    assert paths == ['aqis_lab/pkg/alpha.py', 'tests/aqis_lab/test_gamma.py', 'tools/beta.py']


def test_FR_1_0_03_kit_staging_is_scanned_when_present(repo: Path) -> None:
    write(repo, 'kit-staging/staged.py', DOC.format(name='staged'))
    write(repo, 'aqis_lab/pkg/alpha.py', DOC.format(name='alpha'))
    paths = [fact.path for fact in scan(repo)]
    assert paths == ['aqis_lab/pkg/alpha.py', 'kit-staging/staged.py']


def test_FR_1_0_03_missing_trees_are_absent_not_an_error(repo: Path) -> None:
    write(repo, 'aqis_lab/only.py', DOC.format(name='only'))
    assert [fact.path for fact in scan(repo)] == ['aqis_lab/only.py']


def test_FR_1_0_03_sorting_is_independent_of_filesystem_order(repo: Path) -> None:
    for name in ('b_mid.py', 'a_first.py', 'c_last.py'):
        write(repo, f'aqis_lab/{name}', DOC.format(name=name))
    first = [fact.path for fact in scan(repo)]
    second = [fact.path for fact in scan(repo)]
    assert first == second == sorted(first)


def test_FR_1_0_03_a_syntax_error_is_a_parse_error_not_a_crash(repo: Path) -> None:
    write(repo, 'aqis_lab/good.py', DOC.format(name='good'))
    write(repo, 'aqis_lab/broken.py', '"""Broken."""\n\ndef broken(:\n    return 1\n')
    facts = facts_by_path(scan(repo))
    broken = facts['aqis_lab/broken.py']
    assert broken.parse_error is not None
    assert broken.parse_error.path == 'aqis_lab/broken.py'
    assert broken.parse_error.line == 3
    assert broken.parse_error.render().startswith('aqis_lab/broken.py:3: ')
    assert broken.symbols == ()
    assert facts['aqis_lab/good.py'].parse_error is None


def test_FR_1_0_03_a_module_without_docstring_has_none(repo: Path) -> None:
    write(repo, 'aqis_lab/plain.py', 'VALUE = 1\n')
    (fact,) = scan(repo)
    assert fact.docstring is None
    assert fact.parse_error is None


def test_FR_1_0_03_docstring_is_kept_raw(repo: Path) -> None:
    write(repo, 'aqis_lab/raw.py', '"""  Indented purpose.\n\n  Body line.\n  """\n')
    (fact,) = scan(repo)
    assert fact.docstring == '  Indented purpose.\n\n  Body line.\n  '


def test_FR_1_0_03_public_symbols_include_methods_of_public_classes(repo: Path) -> None:
    source = (DOC.format(name='mod') +
              'from __future__ import annotations\n\n\n'
              'def top_fn(value: int) -> int:\n    return value\n\n\n'
              'class Thing:\n'
              '    def run(self, value: int) -> int:\n        return top_fn(value)\n\n'
              '    def _hidden(self) -> None:\n        return None\n')
    write(repo, 'aqis_lab/mod.py', source)
    (fact,) = scan(repo)
    names = [(symbol.name, symbol.kind) for symbol in fact.symbols]
    assert names == [('top_fn', 'function'), ('Thing', 'class'), ('Thing.run', 'method')]


def test_FR_1_0_03_private_names_are_excluded(repo: Path) -> None:
    source = (DOC.format(name='mod') +
              'def _private_fn() -> None:\n    return None\n\n\n'
              'class _Private:\n    def method(self) -> None:\n        return None\n')
    write(repo, 'aqis_lab/mod.py', source)
    (fact,) = scan(repo)
    assert fact.symbols == ()


def test_FR_1_0_03_first_signature_line_is_the_stripped_source_line(repo: Path) -> None:
    source = (DOC.format(name='mod') +
              'from __future__ import annotations\n\n\n'
              'def top_fn(value: int) -> int:\n    return value\n')
    write(repo, 'aqis_lab/mod.py', source)
    (fact,) = scan(repo)
    symbol = fact.symbols[0]
    assert symbol.signature == 'def top_fn(value: int) -> int:'
    assert symbol.line == source.splitlines().index('def top_fn(value: int) -> int:') + 1


def test_FR_1_0_03_async_functions_count_as_functions(repo: Path) -> None:
    source = DOC.format(name='mod') + 'async def coro() -> None:\n    return None\n'
    write(repo, 'aqis_lab/mod.py', source)
    (fact,) = scan(repo)
    assert [(symbol.name, symbol.kind) for symbol in fact.symbols] == [('coro', 'function')]


def test_FR_1_0_03_relative_imports_resolve_to_repository_paths(repo: Path) -> None:
    write(repo, 'aqis_lab/pkg/__init__.py', DOC.format(name='pkg'))
    write(repo, 'aqis_lab/pkg/alpha.py', DOC.format(name='alpha'))
    write(repo, 'aqis_lab/pkg/beta.py', DOC.format(name='beta') + 'from .alpha import alpha_fn\n')
    write(repo, 'aqis_lab/pkg/deep/__init__.py', DOC.format(name='deep'))
    write(repo, 'aqis_lab/pkg/deep/gamma.py', DOC.format(name='gamma') + 'from ..alpha import alpha_fn\n')
    facts = facts_by_path(scan(repo))
    assert facts['aqis_lab/pkg/beta.py'].imports == ('aqis_lab/pkg/alpha.py',)
    assert facts['aqis_lab/pkg/deep/gamma.py'].imports == ('aqis_lab/pkg/alpha.py',)


def test_FR_1_0_03_absolute_imports_resolve_to_repository_modules(repo: Path) -> None:
    write(repo, 'aqis_lab/pkg/__init__.py', DOC.format(name='pkg'))
    write(repo, 'aqis_lab/pkg/alpha.py', DOC.format(name='alpha'))
    write(repo, 'tools/uses.py', DOC.format(name='uses') +
           'import aqis_lab.pkg.alpha\nimport aqis_lab.pkg.alpha as other\nfrom aqis_lab.pkg import alpha\n')
    facts = facts_by_path(scan(repo))
    # Claude, 2026-10-12 (FIX-WO03-absolute-from): `from aqis_lab.pkg import alpha` also imports the package itself;
    # the old expectation ('aqis_lab/pkg/alpha.py' alone) held only while absolute from-imports were dropped.
    assert facts['tools/uses.py'].imports == ('aqis_lab/pkg/__init__.py', 'aqis_lab/pkg/alpha.py')


def test_FR_1_0_03_absolute_from_imports_resolve_from_the_repository_root(repo: Path) -> None:
    # Claude, 2026-10-12 (FIX-WO03-absolute-from): `from a.b import c` is absolute; the importer's folder never prefixes it.
    write(repo, 'aqis_lab/pkg/__init__.py', DOC.format(name='pkg'))
    write(repo, 'aqis_lab/pkg/alpha.py', DOC.format(name='alpha'))
    write(repo, 'aqis_lab/gamma.py', DOC.format(name='gamma'))
    write(repo, 'tests/aqis_lab/test_uses.py', DOC.format(name='test_uses') +
          'from aqis_lab.pkg.alpha import alpha_fn\nfrom aqis_lab import gamma\n')
    facts = facts_by_path(scan(repo))
    assert facts['tests/aqis_lab/test_uses.py'].imports == ('aqis_lab/gamma.py', 'aqis_lab/pkg/alpha.py')


def test_FR_1_0_03_reexports_are_listed_by_name(repo: Path) -> None:
    write(repo, 'aqis_lab/pkg/__init__.py', DOC.format(name='pkg') +
           'from .alpha import alpha_fn\nfrom . import beta\n')
    write(repo, 'aqis_lab/pkg/alpha.py', DOC.format(name='alpha'))
    write(repo, 'aqis_lab/pkg/beta.py', DOC.format(name='beta'))
    write(repo, 'aqis_lab/other.py', DOC.format(name='other') + 'from aqis_lab.pkg.alpha import alpha_fn\n')
    facts = facts_by_path(scan(repo))
    assert facts['aqis_lab/pkg/__init__.py'].reexports == ('alpha_fn', 'beta')
    assert facts['aqis_lab/other.py'].reexports == ()


def test_FR_1_0_03_non_repository_imports_are_dropped(repo: Path) -> None:
    write(repo, 'aqis_lab/mod.py', DOC.format(name='mod') +
           'import os\nfrom pathlib import Path\nimport sys as system\n')
    (fact,) = scan(repo)
    assert fact.imports == ()


def test_FR_1_0_03_a_module_does_not_import_itself(repo: Path) -> None:
    write(repo, 'aqis_lab/pkg/__init__.py', DOC.format(name='pkg') + 'from . import alpha\n')
    write(repo, 'aqis_lab/pkg/alpha.py', DOC.format(name='alpha') + 'from . import alpha\n')
    facts = facts_by_path(scan(repo))
    assert facts['aqis_lab/pkg/alpha.py'].imports == ('aqis_lab/pkg/__init__.py',), (
        'from . import alpha resolves to the package __init__ it executes against; '
        'only the self-edge is dropped')
    assert facts['aqis_lab/pkg/__init__.py'].imports == ('aqis_lab/pkg/alpha.py',)


def test_FR_1_0_03_test_functions_are_collected_from_test_files(repo: Path) -> None:
    write(repo, 'tests/aqis_lab/test_mod.py',
           DOC.format(name='test') +
           'def helper() -> None:\n    return None\n\n\n'
           'def test_FR_9_1_01_first() -> None:\n    assert True\n\n\n'
           'def test_FR_9_1_02_second() -> None:\n    assert True\n')
    write(repo, 'tests/aqis_lab/mod_test.py',
           DOC.format(name='test2') + 'def test_FR_9_1_03_suffix() -> None:\n    assert True\n')
    write(repo, 'tests/aqis_lab/helpers.py',
           DOC.format(name='helpers') + 'def test_FR_9_1_04_not_a_test_file() -> None:\n    assert True\n')
    facts = facts_by_path(scan(repo))
    assert facts['tests/aqis_lab/test_mod.py'].tests == ('test_FR_9_1_01_first', 'test_FR_9_1_02_second')
    assert facts['tests/aqis_lab/mod_test.py'].tests == ('test_FR_9_1_03_suffix',)
    assert facts['tests/aqis_lab/helpers.py'].tests == ()


def test_FR_1_0_03_imports_are_sorted_and_unique(repo: Path) -> None:
    write(repo, 'aqis_lab/pkg/__init__.py', DOC.format(name='pkg'))
    write(repo, 'aqis_lab/pkg/alpha.py', DOC.format(name='alpha'))
    write(repo, 'aqis_lab/pkg/beta.py', DOC.format(name='beta'))
    write(repo, 'aqis_lab/pkg/user.py', DOC.format(name='user') +
           'from .beta import beta_fn\nfrom .alpha import alpha_fn\nfrom .beta import beta_fn as again\n')
    facts = facts_by_path(scan(repo))
    assert facts['aqis_lab/pkg/user.py'].imports == ('aqis_lab/pkg/alpha.py', 'aqis_lab/pkg/beta.py')


def test_FR_1_0_03_sources_are_parsed_from_bytes(repo: Path) -> None:
    payload = '"""Crème brûlée docstring."""\nVALUE = "café"\n'.encode('utf-8')
    target = repo / 'aqis_lab' / 'latin.py'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b'# -*- coding: utf-8 -*-\n' + payload)
    (fact,) = scan(repo)
    assert fact.parse_error is None
    assert fact.docstring == 'Crème brûlée docstring.'


def test_FR_1_0_03_is_registry_source_follows_b12_pin_3(repo: Path) -> None:
    write(repo, 'aqis_lab/code.py', DOC.format(name='code'))
    write(repo, 'tools/tool.py', DOC.format(name='tool'))
    write(repo, 'kit-staging/staged.py', DOC.format(name='staged'))
    write(repo, 'tests/aqis_lab/test_code.py', DOC.format(name='test'))
    facts = facts_by_path(scan(repo))
    assert is_registry_source(facts['aqis_lab/code.py'])
    assert is_registry_source(facts['tools/tool.py'])
    assert is_registry_source(facts['kit-staging/staged.py'])
    assert not is_registry_source(facts['tests/aqis_lab/test_code.py'])
