"""Interface view generator for Python source files.

CAPABILITIES:
  CAP-OUTSOURCING-INTERFACE: Generate interface views of Python files
    [tests: test_clean_interface_view, test_unparseable_python_file]
INPUTS AND OUTPUTS: Python code string or path in, string interface view out.
CONTRACTS: none.
INVARIANTS:
  - Interface view contains docstrings, __all__, small top-level constants, public class/function signatures.
  - Function bodies are omitted.
NOT IN SCOPE:
  - Non-Python files.
CHANGE LOG:
  2026-10-10 WO-1.0-02 created.
  2026-10-10 WP-1.0 FR-1.0-02 review fix (Claude): a local name renamed for the compromise scan; no behaviour change.
  2026-10-12 WP-1.0 FR-1.0-03 (Claude): [tests: …] names test functions, not files (gate E3, Lab Map).
"""
from __future__ import annotations

import ast

__all__ = ["interface_view"]


def interface_view(path: str, text: str) -> str:
    """Return an interface view of a Python file in file order without function/method bodies."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return f"# File {path} could not be parsed as Python; raw text follows:\n" + text

    lines: list[str] = []
    doc = ast.get_docstring(tree)
    if doc:
        lines.append(f'"""{doc}"""\n')

    for node in tree.body:
        _process_top_level_node(node, lines)

    return "\n".join(lines).rstrip() + "\n"


def _process_top_level_node(node: ast.AST, lines: list[str]) -> None:
    if isinstance(node, ast.Assign):
        _handle_assign(node, lines)
    elif isinstance(node, ast.AnnAssign):
        _handle_ann_assign(node, lines)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if not node.name.startswith("_"):
            _handle_func_def(node, lines)
    elif isinstance(node, ast.ClassDef):
        if not node.name.startswith("_"):
            _handle_class_def(node, lines)


def _handle_assign(node: ast.Assign, lines: list[str]) -> None:
    is_all = any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
    if is_all:
        lines.append(ast.unparse(node) + "\n")
    elif len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        name = node.targets[0].id
        if name.isupper() and not name.startswith("_") and isinstance(node.value, ast.Constant):
            if len(repr(node.value.value)) < 80:
                lines.append(ast.unparse(node) + "\n")


def _handle_ann_assign(node: ast.AnnAssign, lines: list[str]) -> None:
    if isinstance(node.target, ast.Name):
        name = node.target.id
        if name.isupper() and not name.startswith("_") and node.value is not None:
            if isinstance(node.value, ast.Constant) and len(repr(node.value.value)) < 80:
                lines.append(ast.unparse(node) + "\n")


def _handle_func_def(node: ast.FunctionDef | ast.AsyncFunctionDef, lines: list[str], indent: str = "") -> None:
    sig = _format_func_sig(node, indent=indent)
    doc = ast.get_docstring(node)
    ind = indent or ""
    if doc:
        lines.append(f'{sig}\n{ind}    """{doc}"""\n{ind}    ...\n')
    else:
        lines.append(f"{sig}\n{ind}    ...\n")


def _handle_class_def(node: ast.ClassDef, lines: list[str]) -> None:
    bases = [ast.unparse(b) for b in node.bases]
    base_str = f"({', '.join(bases)})" if bases else ""
    lines.append(f"class {node.name}{base_str}:")
    class_doc = ast.get_docstring(node)
    if class_doc:
        lines.append(f'    """{class_doc}"""')

    has_body = _format_class_body(node, lines)
    if not has_body and not class_doc:
        lines.append("    ...")
    lines.append("\n")


def _format_class_body(node: ast.ClassDef, lines: list[str]) -> bool:
    has_body = False
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            if not item.target.id.startswith("_"):
                lines.append(f"    {ast.unparse(item)}")
                has_body = True
        elif isinstance(item, ast.Assign):
            for t in item.targets:
                if isinstance(t, ast.Name) and not t.id.startswith("_"):
                    lines.append(f"    {ast.unparse(item)}")
                    has_body = True
                    break
        elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not item.name.startswith("_"):
                has_body = True
                _handle_func_def(item, lines, indent="    ")
    return has_body


def _format_func_sig(node: ast.FunctionDef | ast.AsyncFunctionDef, indent: str = "") -> str:
    signature_only = ast.FunctionDef(
        name=node.name,
        args=node.args,
        body=[ast.Pass()],
        decorator_list=node.decorator_list,
        returns=node.returns,
        type_comment=node.type_comment,
    ) if isinstance(node, ast.FunctionDef) else ast.AsyncFunctionDef(
        name=node.name,
        args=node.args,
        body=[ast.Pass()],
        decorator_list=node.decorator_list,
        returns=node.returns,
        type_comment=node.type_comment,
    )
    ast.copy_location(signature_only, node)
    ast.fix_missing_locations(signature_only)
    unparsed = ast.unparse(signature_only)
    first_line = unparsed.split("\n")[0]
    if first_line.endswith(":"):
        first_line = first_line[:-1]
    if indent:
        first_line = "\n".join(f"{indent}{l}" for l in first_line.split("\n"))
    return first_line + ":"
