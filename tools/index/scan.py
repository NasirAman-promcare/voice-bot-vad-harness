"""Walk the lab trees and extract module facts with ast, never importing the scanned code.

CAPABILITIES:
  CAP-INDEX-002: scan() walks aqis_lab/, tools/, tests/aqis_lab/ and (when present) kit-staging/
  of a repository root; for each Python module it records its repository-relative path, docstring
  (or None), public symbols (name, kind, first signature line, line number; methods of public
  classes as Class.method), imports resolved to repository modules, re-exports by name, test
  function names and parse errors as path:line: message [tests: test_FR_1_0_03_walks_the_three_trees_and_skips_fixtures,
  test_FR_1_0_03_missing_trees_are_absent_not_an_error, test_FR_1_0_03_sorting_is_independent_of_filesystem_order,
  test_FR_1_0_03_a_syntax_error_is_a_parse_error_not_a_crash, test_FR_1_0_03_a_module_without_docstring_has_none,
  test_FR_1_0_03_public_symbols_include_methods_of_public_classes,
  test_FR_1_0_03_private_names_are_excluded, test_FR_1_0_03_first_signature_line_is_the_stripped_source_line,
  test_FR_1_0_03_relative_imports_resolve_to_repository_paths,
  test_FR_1_0_03_absolute_imports_resolve_to_repository_modules,
  test_FR_1_0_03_reexports_are_listed_by_name, test_FR_1_0_03_non_repository_imports_are_dropped,
  test_FR_1_0_03_test_functions_are_collected_from_test_files, test_FR_1_0_03_imports_are_sorted_and_unique,
  test_FR_1_0_03_sources_are_parsed_from_bytes]
INPUTS AND OUTPUTS: a repository root path in; a tuple of ModuleFacts out, sorted by path.
  No filesystem writes, no network.
CONTRACTS: docs/process/CHANGE_CONTROL.md section 1 (docstrings feed headers.parse_header);
  WO-1.0-03 B12 pins 2 (trees, skips, bytes) and 3 (registry sources are the caller's filter).
INVARIANTS:
  - Deterministic: sorted directory iteration, sorted imports, no clock, no environment reads.
  - Pure analysis: nothing under the root is imported, executed or evaluated.
  - Every source is read as bytes so a PEP 263 coding line is honoured.
NOT IN SCOPE:
  - Header parsing (headers.py), registry (registry.py), rendering (render.py), impact (impact.py).
CHANGE LOG:
  2026-10-12 WP-1.0 FR-1.0-03 created.
  2026-10-12 WP-1.0 WO-1.0-03 (Claude, FIX-WO03-absolute-from): an absolute `from a.b import c` resolves from
    the repository root; the importer's folder no longer prefixes it."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

__all__ = [
    'SCAN_TREES',
    'SKIP_DIRS',
    'ModuleFacts',
    'ParseError',
    'Symbol',
    'is_registry_source',
    'scan',
]

SCAN_TREES: tuple[str, ...] = ('aqis_lab', 'tools', 'tests/aqis_lab', 'kit-staging')

REGISTRY_TREES: tuple[str, ...] = ('aqis_lab', 'tools', 'kit-staging')

SKIP_DIRS: frozenset[str] = frozenset({'__pycache__', 'fixtures'})

_TEST_FILE_PREFIX = 'test_'
_TEST_FILE_SUFFIX = '_test'


@dataclass(frozen=True)
class Symbol:
    """One public class or function of a module; methods of public classes as Class.method."""
    name: str
    kind: str
    signature: str
    line: int


@dataclass(frozen=True)
class ParseError:
    """A module whose source does not parse; message follows ast's path:line: message shape."""
    path: str
    line: int
    message: str

    def render(self) -> str:
        """The B9 report line: path:line: message."""
        return f'{self.path}:{self.line}: {self.message}'


@dataclass(frozen=True)
class ModuleFacts:
    """What one module file contributes to the index.

    reexports holds the names a `from .sibling import name` statement re-exports, for E4."""
    path: str
    docstring: str | None
    symbols: tuple[Symbol, ...] = ()
    imports: tuple[str, ...] = ()
    reexports: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()
    parse_error: ParseError | None = None
    header_missing: tuple[str, ...] = field(default_factory=tuple, compare=False)


def is_registry_source(facts: ModuleFacts) -> bool:
    """True when the module lives in a tree whose CAPABILITIES feed the registry (B12 pin 3)."""
    return facts.path.split('/', 1)[0] in REGISTRY_TREES


def _skip_directory(name: str) -> bool:
    """True for directories the scan never enters: dot folders, caches and fixture data."""
    return name.startswith('.') or name in SKIP_DIRS


def _iter_module_paths(root: Path) -> list[tuple[str, Path]]:
    """(repository-relative POSIX path, absolute path) for every scannable module, sorted."""
    found: list[tuple[str, Path]] = []
    for tree in SCAN_TREES:
        base = root / tree
        if not base.is_dir():
            continue
        stack: list[Path] = [base]
        while stack:
            current = stack.pop()
            entries = sorted(current.iterdir(), key=lambda entry: entry.name)
            dirs: list[Path] = []
            for entry in entries:
                if entry.is_dir():
                    if not _skip_directory(entry.name):
                        dirs.append(entry)
                elif entry.suffix == '.py':
                    found.append((entry.relative_to(root).as_posix(), entry))
            stack.extend(reversed(dirs))
    found.sort(key=lambda pair: pair[0])
    return found


def _module_index(paths: list[tuple[str, Path]]) -> dict[str, str]:
    """Importable dotted name (and its package prefixes) -> repository-relative path."""
    index: dict[str, str] = {}
    for rel, _ in paths:
        parts = rel[:-3].split('/')
        if parts[-1] == '__init__':
            parts = parts[:-1]
        for cut in range(len(parts), 0, -1):
            index.setdefault('.'.join(parts[:cut]), rel)
    return index


def _resolve_import(module_index: dict[str, str], from_rel: str, node: ast.ImportFrom) -> set[str]:
    """Repository module paths that one `from ... import ...` statement can refer to (E2, E4)."""
    base_parts = from_rel[:-3].split('/')
    if base_parts[-1] == '__init__':
        base_parts = base_parts[:-1]
    else:
        base_parts = base_parts[:-1]
    if node.level:
        base_parts = base_parts[: len(base_parts) - (node.level - 1)]
    else:
        base_parts = []
    root_parts = base_parts + (node.module.split('.') if node.module else [])
    resolved: set[str] = set()
    root_name = '.'.join(root_parts)
    if root_name in module_index:
        resolved.add(module_index[root_name])
    for alias in node.names:
        candidate = '.'.join([*root_parts, alias.name]) if root_parts else alias.name
        if candidate in module_index:
            resolved.add(module_index[candidate])
    return resolved


def _resolve_plain_import(module_index: dict[str, str], node: ast.Import) -> set[str]:
    """Repository module paths behind an `import a.b` statement."""
    resolved: set[str] = set()
    for alias in node.names:
        name = alias.name
        while name:
            if name in module_index:
                resolved.add(module_index[name])
                break
            name = name.rpartition('.')[0]
    return resolved


def _reexported_names(from_rel: str, node: ast.ImportFrom) -> tuple[str, ...]:
    """Names a package __init__ re-exports from a sibling module with `from .x import name` (E4)."""
    if node.level == 0:
        return ()
    if not from_rel.endswith('/__init__.py'):
        return ()
    return tuple(alias.name for alias in node.names if alias.name != '*')


def _first_signature_line(lines: list[str], node: ast.AST) -> str:
    """The stripped first source line of a def or class definition (B12 pin 12)."""
    lineno = getattr(node, 'lineno', 1)
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].strip()
    return ''


def _public_symbols(tree: ast.Module, lines: list[str]) -> tuple[Symbol, ...]:
    """Public classes and functions, with public methods of public classes as Class.method (B3)."""
    symbols: list[Symbol] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith('_'):
            symbols.append(Symbol(node.name, 'function', _first_signature_line(lines, node), node.lineno))
        elif isinstance(node, ast.ClassDef) and not node.name.startswith('_'):
            symbols.append(Symbol(node.name, 'class', _first_signature_line(lines, node), node.lineno))
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and not sub.name.startswith('_'):
                    symbols.append(Symbol(f'{node.name}.{sub.name}', 'method',
                                          _first_signature_line(lines, sub), sub.lineno))
    return tuple(symbols)


def _test_functions(tree: ast.Module) -> tuple[str, ...]:
    """Module-level test function names, in source order (used by TESTMAP and impact)."""
    return tuple(node.name for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test'))


def _parse_module(rel: str, path: Path, module_index: dict[str, str]) -> ModuleFacts:
    """Parse one module file into ModuleFacts; a syntax error becomes a ParseError, never a crash."""
    source = path.read_bytes()
    try:
        tree = ast.parse(source, filename=rel)
    except SyntaxError as exc:
        line = exc.lineno if exc.lineno is not None else 0
        message = exc.msg if exc.msg else 'syntax error'
        return ModuleFacts(path=rel, docstring=None,
                           parse_error=ParseError(path=rel, line=line, message=message))
    except ValueError as exc:
        return ModuleFacts(path=rel, docstring=None,
                           parse_error=ParseError(path=rel, line=0, message=str(exc)))
    text = source.decode('utf-8', errors='replace')
    lines = text.splitlines()
    docstring = ast.get_docstring(tree, clean=False)
    imports: set[str] = set()
    reexports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.update(_resolve_plain_import(module_index, node))
        elif isinstance(node, ast.ImportFrom):
            imports.update(_resolve_import(module_index, rel, node))
            reexports.extend(_reexported_names(rel, node))
    imports.discard(rel)
    is_test_file = PurePosixPath(rel).name.startswith(_TEST_FILE_PREFIX) or \
        PurePosixPath(rel).name.endswith(f'{_TEST_FILE_SUFFIX}.py')
    return ModuleFacts(
        path=rel,
        docstring=docstring,
        symbols=_public_symbols(tree, lines),
        imports=tuple(sorted(imports)),
        reexports=tuple(reexports),
        tests=_test_functions(tree) if is_test_file else (),
    )


def scan(repo_root: Path | str) -> tuple[ModuleFacts, ...]:
    """Facts for every module under the scan trees of repo_root, sorted by repository-relative path.

    Never imports the scanned code. A file that fails to parse contributes a ModuleFacts whose
    parse_error names path:line: message; the other files are still scanned (B9)."""
    root = Path(repo_root)
    paths = _iter_module_paths(root)
    module_index = _module_index(paths)
    return tuple(_parse_module(rel, path, module_index) for rel, path in paths)
