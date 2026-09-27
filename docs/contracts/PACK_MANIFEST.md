# Pack manifest contract, version 1.0

Schema: `aqis_lab/contracts/schemas/pack_manifest.v1.json` (JSON Schema 2020-12, `$id` `urn:aqis-lab:contracts:pack_manifest:1.0`). Validator: `aqis_lab.contracts.validate.validate_manifest`. Introduced by WP-0.2 (FR-0.2-03).

## Purpose
A pack is a fixed set of test clips stored in archives. Its manifest lists every clip with where it came from, its licence, its consent reference where one is needed, its audio format, its hash and where it sits in which archive. The pack builder (WP-0.4) writes manifests; runners read them; run cards point to one by `manifest_id`, `version` and SHA-256.

## File format
- One JSON object, UTF-8. Strict JSON: no `NaN`, `Infinity` or duplicate keys; numbers must be finite; integers are written without a fraction or exponent.
- Every object is closed (a field not listed below is an error), except a clip's `recipe`, which may hold any members in v1.0.

## Fields
Paths are JSON Pointers from the record root; `*` means any array item.

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `/schema_version` | string, `"1.0"` | yes | Contract version, `<major>.<minor>` (approved deviation D1). |
| `/manifest_id` | lowercase letters, digits and hyphens | yes | Stable pack name, such as `smoke`; the same across versions of the pack. |
| `/version` | semantic version 2.0.0, ASCII digits | yes | Pack version, such as `1.0.0` or `1.1.0-rc.1`. |
| `/purpose` | non-empty string | yes | What the pack is for. |
| `/created_utc` | `YYYY-MM-DDTHH:MM:SS[.fraction]Z`, a real date and time | yes | When the manifest was written. |
| `/clips` | array of clip objects, at least one | yes | The clips of the pack. |
| `/clips/*/clip_id` | lowercase letters, digits and hyphens | yes | Clip identifier; unique in the manifest (and across the registry). |
| `/clips/*/source` | lowercase letters, digits and hyphens | yes | Where the clip comes from, such as `librispeech`. The values `owner` and `campaign` mark owner and campaign recordings. |
| `/clips/*/source_ref` | non-empty string | yes | Reference inside the source, such as the original file. |
| `/clips/*/licence` | non-empty string | yes | Licence of the clip. |
| `/clips/*/speaker_id` | non-empty string or null | yes | Speaker identifier; null for non-speech clips (noise, music, silence). |
| `/clips/*/consent_ref` | non-empty string or null | yes | Consent reference; must be a string for owner and campaign recordings. |
| `/clips/*/split` | lowercase letters, digits and hyphens | yes | Split or category, such as `test-clean` or `non-speech`. |
| `/clips/*/duration_s` | number > 0 | yes | Duration in seconds. |
| `/clips/*/sample_rate_hz` | integer ≥ 1 | yes | Sample rate in Hz. |
| `/clips/*/channels` | integer ≥ 1 | yes | Number of audio channels. |
| `/clips/*/sha256` | 64 lowercase hex characters | yes | SHA-256 of the clip file's bytes. |
| `/clips/*/archive` | archive file name | yes | Name of the archive holding the clip; must be listed in `archives`. |
| `/clips/*/member_path` | relative POSIX path | yes | Path of the clip inside its archive: no leading `/`, no `.`, `..` or empty segment, no backslash or control character. |
| `/clips/*/transcript` | string or null | yes | Reference transcript; null when there is none (non-speech clips). |
| `/clips/*/recipe` | object (any members) or null | yes | How a derived clip (such as a noisy mix) was made; null for clips taken as they are. The schema keeps it open; WP-0.4 fills it with recipe v1 (`aqis_lab/packs/schemas/recipe.v1.json`, documented in `docs/data/SMOKE_PACK.md`), which `pack build` and `pack verify` check (WP-0.4 plan deviation D2). |
| `/clips/*/tags` | array of unique non-empty strings (may be empty) | yes | Free labels. |
| `/archives` | array of archive objects, at least one | yes | The archives holding the clips. |
| `/archives/*/name` | file name: one path segment, not `.` or `..`, no `/`, backslash or control character | yes | Archive file name; unique in the manifest. |
| `/archives/*/sha256` | 64 lowercase hex characters | yes | SHA-256 of the archive file's bytes. |
| `/archives/*/bytes` | integer ≥ 0 | yes | Archive size in bytes. |
| `/archives/*/n_members` | integer ≥ 0 | yes | Number of members in the archive. |

## Rules across fields
- A clip whose `source` is `owner` or `campaign` must have a `consent_ref` string (approved question 4).
- `clip_id` is unique among the clips; archive `name` is unique among the archives. A repeat is reported at the later item.
- Every clip's `archive` is the `name` of one listed archive. This is judged when every archive has a string name (a nameless entry is reported itself, and might be the one a clip names).
- A run card's `pack.sha256` is the SHA-256 of this manifest's canonical JSON (see RUN_CARD.md), so the manifest file's formatting does not change it.

## Example
`tests/aqis_lab/fixtures/contracts/valid_manifest.json` (illustrative values, not a built pack). Invalid example: `invalid_manifest_fields.json`.

## Validating
- Python: `validate_manifest(manifest)` returns `None` or raises `ContractValidationError` listing every failing field by JSON Pointer.
- Command line: `python -m aqis_lab contracts validate <file> --kind manifest` prints `record 1: OK` or one `record 1: INVALID <pointer>: <message>` per failing field, then a summary; exit code 0 valid, 1 invalid or empty, 2 usage error or unreadable file.

## Versioning and change policy
- The version is `<major>.<minor>` in the manifest's `schema_version` and in the schema's `$id`, `urn:aqis-lab:contracts:pack_manifest:1.0`. The schema file name carries the major version: `pack_manifest.v1.json`.
- **Minor version**: additions that every existing valid manifest survives: a new optional field, a new enum value, or members defined inside a previously open object (such as `recipe`). The v1 file always describes the newest v1 minor version and accepts every v1 minor version up to it. A validator rejects a manifest with a newer minor version than its own, with a message saying to update aqis_lab.
- **Major version**: anything else: a removed or renamed field, a changed type or meaning, a field that becomes required, a removed enum value. A new major version gets a new file (`pack_manifest.v2.json`); the old file stays so that old manifests still validate. A validator rejects an unknown major version, naming the major versions it knows.
- The contract document, the schema, the fixtures and the tests change in the same commit. A test (FR-0.2-07) keeps the fields in this document and in the schema identical.
