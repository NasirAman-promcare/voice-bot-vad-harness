"""Interface view generator for Python source files.

CAPABILITIES:
  CAP-OUTSOURCING-INTERFACE: Generate interface views of Python files [tests: test_interface.py, test_acceptance_wo_1_0_02.py]
INPUTS AND OUTPUTS: Python code string or path in, string interface view out.
CONTRACTS: none.
INVARIANTS:
  - Interface view contains docstrings, __all__, small top-level constants, public class/function signatures.
  - Function bodies are omitted.
NOT IN SCOPE:
  - Non-Python files.
CHANGE LOG:
  2026-10-10 WO-1.0-02 created.
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

    # 1. Module docstring
    doc = ast.get_docstring(tree)
    if doc:
        lines.append(f'"""{doc}"""\n')

    for node in tree.body:
        # 2. __all__ or Top-level constants whose literal value is under 80 characters
        if isinstance(node, ast.Assign):
            is_all = any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
            if is_all:
                lines.append(ast.unparse(node) + "\n")
            elif len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name.isupper() and not name.startswith("_"):
                    if isinstance(node.value, ast.Constant):
                        val_str = repr(node.value.value)
                        if len(val_str) < 80:
                            lines.append(ast.unparse(node) + "\n")
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                name = node.target.id
                if name.isupper() and not name.startswith("_") and node.value is not None:
                    if isinstance(node.value, ast.Constant):
                        val_str = repr(node.value.value)
                        if len(val_str) < 80:
                            lines.append(ast.unparse(node) + "\n")

        # 3. Public functions
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                sig = _format_func_sig(node)
                doc = ast.get_docstring(node)
                if doc:
                    lines.append(f'{sig}\n    """{doc}"""\n    ...\n')
                else:
                    lines.append(f"{sig}\n    ...\n")

        # 4. Public classes
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                bases = [ast.unparse(b) for b in node.bases]
                base_str = f"({', '.join(bases)})" if bases else ""
                lines.append(f"class {node.name}{base_str}:")
                class_doc = ast.get_docstring(node)
                if class_doc:
                    lines.append(f'    """{class_doc}"""')

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
                            msig = _format_func_sig(item, indent="    ")
                            mdoc = ast.get_docstring(item)
                            if mdoc:
                                lines.append(f'{msig}\n        """{mdoc}"""\n        ...')
                            else:
                                lines.append(f"{msig}\n        ...")
                if not has_body and not class_doc:
                    lines.append("    ...")
                lines.append("\n")

    return "\n".join(lines).rstrip() + "\n"


def _format_func_sig(node: ast.FunctionDef | ast.AsyncFunctionDef, indent: str = "") -> str:
    dummy = ast.FunctionDef(
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
    ast.copy_location(dummy, node)
    ast.fix_missing_locations(dummy)
    unparsed = ast.unparse(dummy)
    first_line = unparsed.split("\n")[0]
    if first_line.endswith(":"):
        first_line = first_line[:-1]
    if indent:
        first_line = "\n".join(f"{indent}{l}" for l in first_line.split("\n"))
    return first_line + ":"
