"""
corpus package initialization.

Exposes the canonical manifest loader, data structures, and validation errors
for the VAD benchmarking and latency harness.
"""

from corpus.manifest import (
    VALID_CATEGORIES,
    CorpusCategory,
    Manifest,
    ManifestEntry,
    ManifestValidationError,
    load_manifest,
    parse_and_validate_manifest,
)

__all__ = [
    "VALID_CATEGORIES",
    "CorpusCategory",
    "Manifest",
    "ManifestEntry",
    "ManifestValidationError",
    "load_manifest",
    "parse_and_validate_manifest",
]