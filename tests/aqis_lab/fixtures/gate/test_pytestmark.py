"""Gate fixture: module-level markers that skip every test."""
import pytest

pytestmark = pytest.mark.skip(reason="fixture")


def test_param_marks():
    params = [pytest.param(1, marks=pytest.mark.skipif(True, reason="fixture"))]
    assert len(params) == 1
