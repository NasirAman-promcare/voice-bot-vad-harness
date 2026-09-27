# Run card contract, version 1.0

Schema: `aqis_lab/contracts/schemas/run_card.v1.json` (JSON Schema 2020-12, `$id` `urn:aqis-lab:contracts:run_card:1.0`). Validator: `aqis_lab.contracts.validate.validate_run_card`. ID: `aqis_lab.contracts.canonical.compute_run_card_id`. Introduced by WP-0.2 (FR-0.2-02, FR-0.2-05).

## Purpose
A run card records everything that decides a run's result: the pack, the model and its settings, the processing steps, the mode, the machine, the seed, the text normaliser, the dependency lock and the code commit. Every event and every score row points to its run card through `run_card_id`, so any number can be traced back to what produced it.

## File format
- One JSON object, UTF-8. Strict JSON: no `NaN`, `Infinity` or duplicate keys; numbers must be finite; `seed` is written without a fraction or exponent.
- Every object is closed (a field not listed below is an error), except `model.settings` and each step's `params`, which may hold any members.

## Fields
Paths are JSON Pointers from the record root; `*` means any array item.

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `/schema_version` | string, `"1.0"` | yes | Contract version, `<major>.<minor>` (approved deviation D1). |
| `/run_card_id` | 64 lowercase hex characters | yes | SHA-256 of the canonical card without `run_card_id`, `created_utc` and `notes` (below). |
| `/pack` | object, or null only when `mode` is `human_session` | yes | The pack manifest the run reads. |
| `/pack/manifest_id` | lowercase letters, digits and hyphens | yes | `manifest_id` of the pack manifest. |
| `/pack/version` | semantic version | yes | `version` of the pack manifest. |
| `/pack/sha256` | 64 lowercase hex characters | yes | SHA-256 of the manifest's canonical JSON (`sha256_canonical(manifest)`), so re-formatting the file does not change it. |
| `/model` | object | yes | The model under test. |
| `/model/family` | non-empty string | yes | Model family, such as `vosk`. |
| `/model/version` | non-empty string or null | yes | Model version; null when only the checksum identifies the model. |
| `/model/checksum` | 64 lowercase hex characters, or null | yes | SHA-256 of the model files; null when the version identifies the model. |
| `/model/name` | non-empty string | yes | Model name. |
| `/model/settings` | object (any members) | yes | Model settings as used by the run. |
| `/processing` | object | yes | Ordered fix steps applied before each path's component. |
| `/processing/vad` | array of steps (may be empty) | yes | Steps before voice activity detection, in order. |
| `/processing/vad/*/name` | non-empty string | yes (in each step) | Step name. |
| `/processing/vad/*/params` | object (any members) | yes (in each step) | Step parameters. |
| `/processing/stt` | array of steps (may be empty) | yes | Steps before speech-to-text, in order. |
| `/processing/stt/*/name` | non-empty string | yes (in each step) | Step name. |
| `/processing/stt/*/params` | object (any members) | yes (in each step) | Step parameters. |
| `/processing/emotion` | array of steps (may be empty) | yes | Steps before emotion recognition, in order. |
| `/processing/emotion/*/name` | non-empty string | yes (in each step) | Step name. |
| `/processing/emotion/*/params` | object (any members) | yes (in each step) | Step parameters. |
| `/mode` | one of `batch`, `realspeed_cpu`, `gpu_compute_delay`, `tier2_live`, `nearlive_replay`, `human_session` | yes | How the run is executed. |
| `/machine` | object | yes | Where the run executes; filled by `aqis_lab.platform` (WP-0.5). |
| `/machine/platform` | one of `cloud-vm`, `colab`, `kaggle`, `oracle` | yes | Lab platform. |
| `/machine/gpu` | non-empty string or null | yes | GPU type, or null without a GPU. |
| `/machine/cpu_model` | non-empty string | yes | CPU model name. |
| `/machine/architecture` | non-empty string | yes | Machine architecture, such as `x86_64` or `aarch64`. |
| `/machine/os` | non-empty string | yes | Operating system name and version. |
| `/machine/python_version` | `X.Y.Z`, optionally followed by a suffix such as `rc1` | yes | Python version. |
| `/seed` | integer ≥ 0 | yes | Seed for every random step of the run. |
| `/normaliser` | object, or null for runs that produce no text | yes | Text normaliser used for scoring. |
| `/normaliser/name` | non-empty string | yes | Normaliser name. |
| `/normaliser/version` | non-empty string | yes | Normaliser version. |
| `/lock` | object | yes | Dependency lock the run's environment was installed from. |
| `/lock/file` | repository-relative POSIX path | yes | Lock file path: no leading `/`, no `.`, `..` or empty segment, no backslash. |
| `/lock/sha256` | 64 lowercase hex characters | yes | SHA-256 of the lock file's bytes. |
| `/git` | object | yes | Code the run used. |
| `/git/commit` | 40 or 64 lowercase hex characters | yes | Full commit hash. |
| `/git/dirty` | boolean | yes | True when the checkout had uncommitted changes. |
| `/created_utc` | `YYYY-MM-DDTHH:MM:SS[.fraction]Z`, a real date and time | yes | When the card was written; not part of `run_card_id`. |
| `/notes` | string (may be empty) | yes | Free text; not part of `run_card_id`. |

## Rules across fields
- `pack` may be null only when `mode` is `human_session`: a live human session has no pack.
- `model.version` and `model.checksum` cannot both be null.
- `run_card_id` must equal the SHA-256 (lowercase hex) of the canonical JSON of the card without `run_card_id`, `created_utc` and `notes`. Canonical JSON: keys sorted, separators `,` and `:` with no spaces, UTF-8 without `\u` escapes for non-ASCII text, no NaN or Infinity. Every other field, including `schema_version` and the order of processing steps, is part of the ID. `20260927` and `20260927.0` are different JSON and give different IDs, which is why integers are strict.

## Example
`tests/aqis_lab/fixtures/contracts/valid_run_card.json` (illustrative values). Invalid examples: `invalid_run_card_fields.json`, `invalid_run_card_id.json`.

## Validating
- Python: `validate_run_card(card)` returns `None` or raises `ContractValidationError` listing every failing field by JSON Pointer, including `/run_card_id` when the ID does not match the content. `compute_run_card_id(card)` gives the defined ID.
- Command line: `python -m aqis_lab contracts validate <file> --kind run_card` prints `record 1: OK` or one `record 1: INVALID <pointer>: <message>` per failing field, then a summary; exit code 0 valid, 1 invalid or empty, 2 usage error or unreadable file.

## Versioning and change policy
- The version is `<major>.<minor>` in the card's `schema_version` and in the schema's `$id`, `urn:aqis-lab:contracts:run_card:1.0`. The schema file name carries the major version: `run_card.v1.json`.
- **Minor version**: additions that every existing valid card survives: a new optional field, a new enum value (such as a mode or platform), or members defined inside a previously open object. The v1 file always describes the newest v1 minor version and accepts every v1 minor version up to it. A validator rejects a card with a newer minor version than its own, with a message saying to update aqis_lab.
- **Major version**: anything else: a removed or renamed field, a changed type or meaning, a field that becomes required, a removed enum value, or a changed `run_card_id` definition. A new major version gets a new file (`run_card.v2.json`); the old file stays so that old cards still validate. A validator rejects an unknown major version, naming the major versions it knows.
- The contract document, the schema, the fixtures and the tests change in the same commit. A test (FR-0.2-07) keeps the fields in this document and in the schema identical.
