# Results store

The results store keeps every result row the lab produces, append-only, in one folder per run card, so any row can be traced back to what produced it (`python -m aqis_lab trace`). Built by WP-0.6 (FR-0.6-02, FR-0.6-03). Code: `aqis_lab/results/` (`store.py`, `ingest.py`, `views.py`), `aqis_lab/commands/results.py`, `aqis_lab/trace.py`.

## Usage
```bash
.venv/bin/python -m aqis_lab results add --run <finished run folder>
.venv/bin/python -m aqis_lab results add --scores <score folder> [--run-card <run_card.json>]
.venv/bin/python -m aqis_lab results query --run-card <run_card_id>
.venv/bin/python -m aqis_lab trace <result_row_id>
```
Every command takes `--store DIR`; the default is `data/raw/aqis_lab/results/` (git-ignored), the same folder as `paths.results_store` in `config/aqis_lab/oracle.yaml`. If you change that setting, pass the same folder with `--store`.

| Command | Exit 0 | Exit 1 | Exit 2 |
| --- | --- | --- | --- |
| `results add` | Rows stored, or every row already stored | A row is already stored with other content (conflict), or a stored file does not check; nothing was written | Usage or input error: not a finished run, not a score folder, a score folder whose run card is not in the store and no `--run-card`, a store on Google Drive |
| `results query` | The rows are printed | No rows for that run card, or a stored row does not check | A malformed run card ID or no store at `--store` |

Errors start with `ERROR:` on stderr.

## Layout
```text
<store>/STORE.json                                  {"store_schema_version":"1.0"}, written once
<store>/.lock                                       held (flock) during every add, so adds never interleave
<store>/run_card_id=<run_card_id>/run_card.json     the run card, exactly as the source had it, written once
<store>/run_card_id=<run_card_id>/part-<SHA-256>.parquet   one file per add, named after its own SHA-256
```
- **Append-only.** Each add writes at most one new part file per run card. Files are published by writing `<name>.partial`, fsyncing it, hard-linking it to its final name and fsyncing the folder. A hard link fails when the name exists, so **a stored file is never replaced**. Stored files are made read-only (mode 0444).
- **Never overwritten rows.** A row whose identity is already stored with the same content is reported as already stored and not written again. A row whose identity is stored with **other** content is a conflict: the whole add stops with exit 1 and nothing is written.
- **Interrupted adds** leave at most a `.partial` file. Readers and `sync` ignore `.partial` files; the next add removes them while it holds the lock.
- **Local disk only.** The store needs hard links, which Google Drive's FUSE mount does not have, so a store on a Drive mount is refused. `python -m aqis_lab sync` copies the store to `AQIS_LAB/results` on Drive (docs/oracle/ORACLE_RUNBOOK.md).
- **Folder size.** Google Drive slows down past about 10,000 items in one folder; the store has one folder per run card.

## Row kinds and identity
`result_row_id` is the SHA-256 (lowercase hex) of the canonical JSON (keys sorted, separators `,` and `:`, UTF-8) of the row's identity object:

| `kind` | Source (`results add`) | Identity object keys |
| --- | --- | --- |
| `run-result` | `--run DIR`: `results.jsonl` of a finished run folder (docs/runner/RUNNER.md) | `kind`, `run_card_id`, `clip_id`, `task`, `task_version` |
| `score` | `--scores DIR`: `scores.parquet` of a `score` output folder (docs/contracts/SCORE_TABLE.md) | `kind`, `run_card_id`, `clip_id`, `variant`, `normaliser_name`, `normaliser_version`, `ref_sha256` |

So a corrected reference text gives a new score row, while a different result for the same run card and clip is a conflict.

**What `add` accepts.**
- `--run DIR`: a valid `run_card.json`; a `shard_plan.json` naming the same card; a `results.jsonl` whose every line is a strict JSON object of that run card, covering the plan's clips exactly once. An unfinished run has no `results.jsonl` and is refused.
- `--scores DIR`: `summary.json`'s SHA-256 values match `scores.parquet` and `scores.csv`; the table is score table 1.0; all rows name one run card; each clip and variant appears once. That run card must already be in the store (add its run folder first), or be given with `--run-card FILE`.

## Columns
Every part file is Parquet with key-value metadata `aqis_results_store_schema_version` = `"1.0"` and exactly these columns, in this order, none null. Rows in a file are sorted by `kind`, `clip_id`, `result_row_id`.

| Column | Type | Meaning |
| --- | --- | --- |
| `result_row_id` | `string` | SHA-256 of the identity object's canonical JSON (above) |
| `kind` | `string` | `run-result` or `score` |
| `run_card_id` | `string` | The run card the row belongs to; equals the folder name |
| `clip_id` | `string` | The clip |
| `identity` | `string` | The identity object, canonical JSON |
| `row` | `string` | The source row, whole, as canonical JSON |
| `row_sha256` | `string` | SHA-256 of `row` |
| `source_file` | `string` | `results.jsonl` or `scores.parquet` |
| `source_sha256` | `string` | SHA-256 of that source file's bytes |
| `added_utc` | `string` | When the add ran, UTC ISO 8601 with `Z` |
| `added_by` | `string` | The `version` command's line of the code that added the row (package, commit, Python) |

Readers check every file and row: the metadata and columns, that each file's name still equals its SHA-256, that each row's ID recomputes from its identity, that `row_sha256` matches, and that the identity's `kind`, `run_card_id` and `clip_id` equal the columns and the folder. Any difference is an integrity error, never a silent skip.

## DuckDB views
`aqis_lab.results.views.connect(store)` returns an in-memory DuckDB connection with automatic extension installs and loading switched off (DuckDB 1.5.6 has `parquet` and `json` built in, so nothing is downloaded). It holds three views:

| View | Columns |
| --- | --- |
| `result_rows` | The columns above, from every `part-*.parquet` file |
| `run_cards` | `run_card_id`, `pack_manifest_id`, `pack_version`, `pack_sha256`, `git_commit`, `git_dirty`, `lock_file`, `lock_sha256`, `mode`, `card_json` (the stored file's text), `card_file` |
| `results` | Every `result_rows` column plus the run card's `pack_manifest_id`, `pack_version`, `pack_sha256`, `git_commit`, `git_dirty`, `lock_file`, `lock_sha256`, `mode` |

The views are defined like this (the code lists the files explicitly, so `.partial` files are never read):
```sql
CREATE VIEW result_rows AS SELECT * FROM read_parquet('<store>/run_card_id=*/part-*.parquet');
CREATE VIEW run_cards AS SELECT
  json_extract_string(content, '$.run_card_id') AS run_card_id,
  json_extract_string(content, '$.pack.manifest_id') AS pack_manifest_id,
  json_extract_string(content, '$.pack.version') AS pack_version,
  json_extract_string(content, '$.pack.sha256') AS pack_sha256,
  json_extract_string(content, '$.git.commit') AS git_commit,
  CAST(json_extract(content, '$.git.dirty') AS BOOLEAN) AS git_dirty,
  json_extract_string(content, '$.lock.file') AS lock_file,
  json_extract_string(content, '$.lock.sha256') AS lock_sha256,
  json_extract_string(content, '$.mode') AS mode,
  content AS card_json, filename AS card_file
FROM read_text('<store>/run_card_id=*/run_card.json');
CREATE VIEW results AS SELECT r.*, c.pack_manifest_id, c.pack_version, c.pack_sha256, c.git_commit, c.git_dirty,
  c.lock_file, c.lock_sha256, c.mode
FROM result_rows r LEFT JOIN run_cards c ON c.run_card_id = r.run_card_id;
```
From Python, for example:
```python
from aqis_lab.results.views import connect
con = connect("data/raw/aqis_lab/results")
print(con.sql("SELECT kind, count(*) FROM results GROUP BY kind").fetchall())
```

## Query output
`results query --run-card <id>` prints one canonical JSON object per row (keys sorted, no spaces), sorted by `kind`, `clip_id`, then `result_row_id`. Each object holds the columns above, with `identity` and `row` expanded to JSON objects.

## Trace
`python -m aqis_lab trace <result_row_id>` finds the row through the `results` view and prints its run card, pack manifest ID and version, clip, git commit and lock hash; see `docs/oracle/ORACLE_RUNBOOK.md` and the command's `--help`. Before printing it checks that exactly one row has the ID, that the row checks (above), and that the stored run card validates and has the row's `run_card_id`. Any failed check is `ERROR:` and exit 1.
