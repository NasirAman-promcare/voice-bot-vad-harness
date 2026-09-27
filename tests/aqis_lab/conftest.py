"""Pytest configuration for the AQIS lab tests in tests/aqis_lab/ (FR-0.0-04).

Registers the five lab markers and keeps the gate fixture files out of collection.
This file deliberately does nothing else: it does not change sys.path, add session-wide
collection hooks or define autouse fixtures, so harness tests in tests/regression/ are
discovered and run exactly as before, even when both folders are collected together.
"""

MARKERS = {
    "slow": "long-running test; excluded from the fast suite",
    "gpu": "needs a CUDA GPU; excluded from the fast suite",
    "colab": "runs only on Google Colab; excluded from the fast suite",
    "oracle": "runs only on the Oracle VM; excluded from the fast suite",
    "network": "needs outbound network access; excluded from the fast suite",
}

# Files under fixtures/ are inputs copied into throwaway git repositories, never tests.
collect_ignore = ["fixtures"]


def pytest_configure(config):
    for name, description in MARKERS.items():
        config.addinivalue_line("markers", f"{name}: {description}")
