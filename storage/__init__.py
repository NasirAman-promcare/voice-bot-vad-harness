"""
storage package initialization.

Exposes the canonical results persistence store, raw evaluation record schemas,
and runtime library version inspection utilities.
"""

from storage.results_store import (
    RawEvaluationRecord,
    ResultsStore,
    ResultsStoreError,
    get_installed_library_version,
    get_vad_library_version,
)

__all__ = [
    "RawEvaluationRecord",
    "ResultsStore",
    "ResultsStoreError",
    "get_installed_library_version",
    "get_vad_library_version",
]