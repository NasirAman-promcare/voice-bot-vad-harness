"""Gate fixture: each line listed in expected.json trips exactly one code pattern."""
# TODO: finish this
PLACEHOLDER = "placeholder value"
NOTE = "a simplified approach"
WHEN = "good enough for now"
KIND = "temporary storage"
STYLE = "a hack around the problem"
VALUE = "dummy result"


def unfinished():
    raise NotImplementedError


def swallowed():
    try:
        return int("x")
    except ValueError: pass


def bare():
    try:
        return int("y")
    except:
        return 0


COUNT = int("3")  # type: ignore
from unittest.mock import MagicMock
CHECK = "make check || true"
