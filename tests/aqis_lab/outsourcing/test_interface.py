"""Unit tests for tools.outsourcing.interface.

CAPABILITIES:
  CAP-OUTSOURCING-INTERFACE: Generate interface views of Python files [tests: test_interface.py]
INPUTS AND OUTPUTS: Interface view tests.
CONTRACTS: none.
INVARIANTS: Interface views omit implementation details.
NOT IN SCOPE: I/O.
CHANGE LOG:
  2026-10-10 WO-1.0-02 created.
"""
from __future__ import annotations

from tools.outsourcing.interface import interface_view


def test_clean_interface_view():
    code = '''"""Module docstring."""
from __future__ import annotations

__all__ = ["VALUE", "compute", "MyClass"]

VALUE = 42
LONG_CONST = "x" * 100

def compute(x: int) -> int:
    """Compute something."""
    secret_internal = x + 100
    return secret_internal

class MyClass:
    """Class docstring."""
    field: int

    def method(self) -> None:
        """Method docstring."""
        print("hello")
'''
    view = interface_view("sample.py", code)
    assert '"""Module docstring."""' in view
    assert "__all__ =" in view and "VALUE" in view and "compute" in view
    assert "VALUE = 42" in view
    assert "LONG_CONST" not in view
    assert "def compute(x: int) -> int:" in view
    assert '"""Compute something."""' in view
    assert "secret_internal" not in view
    assert "class MyClass:" in view
    assert "field: int" in view
    assert "def method(self) -> None:" in view
    assert "print(" not in view


def test_unparseable_python_file():
    code = "def invalid_syntax(:"
    view = interface_view("bad.py", code)
    assert "# File bad.py could not be parsed as Python; raw text follows:" in view
    assert code in view
