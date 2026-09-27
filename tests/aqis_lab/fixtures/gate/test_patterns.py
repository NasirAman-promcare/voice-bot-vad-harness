"""Gate fixture: each line listed in expected.json trips exactly one test-integrity pattern."""
import unittest

import pytest


@pytest.mark.skip(reason="fixture")
def test_marked_skip():
    assert 2 == 2


@pytest.mark.skipif(True, reason="fixture")
def test_marked_skipif():
    assert 2 == 2


def test_skip_call():
    pytest.skip("fixture")


@unittest.skip("fixture")
def test_unittest_skip():
    assert 2 == 2


def test_importorskip():
    pytest.importorskip("json")


@pytest.mark.xfail(reason="fixture")
def test_expected_failure():
    assert 2 == 2


def test_trivial_true():
    assert True


def test_trivial_one():
    assert 1
