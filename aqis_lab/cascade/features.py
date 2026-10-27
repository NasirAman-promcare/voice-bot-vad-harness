"""Sprint 3 gate features that need more than the Sprint 1 files: where they are stored and how they are merged.

CAPABILITIES:
  CAP-S3-045: read_features() and merge_features() keep one parquet file of per-turn extra features (non-speech ratio, token confidence,
    entropy-based confidence) keyed by "<slice>:<condition>:<utt_id>"; merging keeps every other row and column [tests:
    test_s3_merging_features_keeps_other_columns]
INPUTS AND OUTPUTS: a path and {key: {column: value}} in; {key: row} out.
CONTRACTS: the file is written through aqis_lab.drive (atomic).
INVARIANTS:
  - This module imports no scorer and no ML library, so a GPU environment without the scoring packages can use it.
NOT IN SCOPE:
  - Computing the features (simulate.compute_nonspeech, confidence.extract).
CHANGE LOG:
  2026-10-28 WP-1.3 created.
"""
from pathlib import Path

from aqis_lab import drive

OPTIONAL_FEATURES = ("nonspeech_ratio", "confidence", "entropy")
FEATURE_FILE = ("cascade", "features.parquet")


def read_features(path):
    path = Path(path)
    if not path.is_file():
        return {}
    import pyarrow.parquet as pq
    return {r["key"]: r for r in pq.read_table(path).to_pylist()}


def merge_features(path, found):
    """Write `found` ({key: {column: value}}) into the feature file, keeping every other row and column."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    path = Path(path)
    rows = read_features(path)
    for key, values in found.items():
        merged = dict(rows.get(key, {"key": key}))
        merged.update(values)
        rows[key] = merged
    columns = ["key", *OPTIONAL_FEATURES]
    sink = pa.BufferOutputStream()
    pq.write_table(pa.Table.from_pylist([{c: r.get(c) for c in columns} for _, r in sorted(rows.items())]), sink, compression="zstd")
    drive.make_dirs(path.parent)
    drive.write_bytes(path, sink.getvalue().to_pybytes())
