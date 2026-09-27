# Source registry format (`data/registry/sources.csv`)

The registry records where every source clip of the lab came from and under what licence (WP-0.4 FR-0.4-01). Packs are built only from registry rows. The file is generated, never edited by hand: `python -m aqis_lab registry build` writes it from the fetched datasets and the local folders that `data/registry/datasets.yaml` names. `python -m aqis_lab registry validate` checks it.

## File format
- UTF-8 CSV with a header row, `\n` line ends and minimal quoting; rows sorted by `clip_id`.
- An empty field means null.
- No field may contain a control character (line breaks and tabs included).
- The header must be exactly the 15 columns below, in this order.

## Columns
The first eight columns are the fields FR-0.4-01 names; the others locate and describe the source file.

| Column | Value | Rule |
| --- | --- | --- |
| `clip_id` | lowercase letters, digits and hyphens | unique in the registry. LibriSpeech `ls-<split>-<utterance>`, MUSAN `musan-<file stem>`, synthetic TTS `tts-smoke-<stem>`, owner recordings `owner-<stem>` |
| `source` | lowercase letters, digits and hyphens | the dataset's source: `librispeech`, `musan`, `tts`; `owner` and `campaign` mark recordings of people |
| `source_ref` | text | path of the file inside its dataset: inside the archive for downloads, inside the repository for local folders |
| `licence` | licence ID | required; must be defined in the licence table of `datasets.yaml` |
| `speaker_id` | text or empty | required for speech clips (the LibriSpeech reader ID; `kokoro-<voice>` for synthetic TTS clips); empty for non-speech |
| `consent_ref` | repository path or empty | required for `owner` and `campaign` recordings, where it must name an existing, non-empty file in the repository; empty for every other source |
| `transcript` | text or empty | required for speech clips (LibriSpeech's trans.txt text verbatim; for synthetic TTS clips the exact TTS input text); empty for non-speech |
| `split` | lowercase letters, digits and hyphens | one of the dataset's splits: `test-clean`, `test-other`, `noise`, `music`, `tts`, `owner` |
| `dataset` | dataset ID | a dataset of `datasets.yaml`; the row's `source` must equal that dataset's source |
| `tags` | tags one space apart, sorted, unique | lowercase letters, digits and hyphens: `background` (free-sound background noises), `genre-<g>` and `vocals-no` (MUSAN music), `synthetic`, `tts` and `voice-<voice>` (TTS clips) |
| `sha256` | 64 lowercase hexadecimal characters | SHA-256 of the source file's bytes; the pack builder refuses a file that no longer matches |
| `sample_rate_hz` | whole number ≥ 1 | always 16000 today: every source must be 16 kHz mono 16-bit, never converted |
| `channels` | whole number ≥ 1 | always 1 today |
| `n_samples` | whole number ≥ 1 | samples per channel; duration = `n_samples / sample_rate_hz` |
| `attribution` | text or empty | per-file attribution when the licence needs one beyond the dataset's (each MUSAN rfm track: title and artist in incompetech's form) |

## Validation
`registry validate` (and every `registry build` and `pack build`) reports every problem as `line <n> column <name>: <reason>`, never only the first:
- a missing licence, or a licence not in the licence table;
- an `owner` or `campaign` row without a consent reference, or one that does not resolve to a non-empty file inside the repository (absolute paths, `..` and folders are rejected);
- a consent reference on any other source;
- a speech row without a transcript or speaker, or a non-speech row with either;
- an invalid or repeated `clip_id`, an unknown dataset, a `source` or `split` that does not match the dataset, badly formed tags, hashes or numbers;
- a wrong header, a row with the wrong number of fields, or a file that is not UTF-8.

Exit codes: 0 valid, 1 invalid, 2 unreadable file or invalid `datasets.yaml`.

## `datasets.yaml` (format 1)
Schema `aqis_lab/registry/schemas/datasets.v1.json`; duplicate keys are rejected; every object is closed.
- `format_version: 1`.
- `generated_licence`: licence of clips the pack builder generates from no third-party material (digital silence): `CC0-1.0`.
- `licences`: licence ID → `name`, `url` (or null), `attribution_required`, `share_alike`, `non_commercial`. A pack spec's licence policy uses the last two.
- `datasets`: dataset ID → entry. Common fields: `type` (`download` or `local`), `importer`, `source`, `kind` (`speech` or `non-speech`), `licence`, `homepage`, `attribution` (the text `LICENCES.md` quotes) and optional `changes`.
  - `download` entries add `url`, `bytes`, `sha256`, `md5` (the publisher's) and `extract` (patterns; `**` crosses folders, `*` stays in one). `registry fetch` downloads into `data/raw/aqis_lab/` (git-ignored), checks size, MD5 and SHA-256 before reading any member, and extracts only matching members.
  - `librispeech`: `split`. Every FLAC needs a line in its chapter's trans.txt and every line a FLAC.
  - `musan`: `subsets`, each with `split`, `licence`, `licence_file_sha256` (the subset's LICENSE file is pinned, so a changed licence statement stops the import), `annotations` (`noise-background-list` or `music-table`) and, for rfm, `titles: rfm-licence` and `attribution_template`.
  - `tts` (local): `folder`, `split`, `clip_prefix`, `speaker_prefix`, `tags` and `generation_record`. The folder holds `NN.wav` synthetic clips, `transcripts.csv` (header `file,text`) and the generation record, a Markdown table with the columns File, Voice, SHA-256 and Text. Every file must appear in both, with the same text and hash.
  - `owner` (local): `folder`, `split`, `clip_prefix`, `consent_file` and `speaker_id`. The folder holds `NN.wav` recordings, `transcripts.csv` and the consent file. Only this importer may produce `owner` or `campaign` rows. Phase 0 has no owner recordings (owner decision, approval `docs/approvals/WP-0.4.md`); the rules and their tests stay for the Phase 1 campaign recordings.
  - Local folders accept only `*.wav` files named with lowercase letters, digits and hyphens plus the listed text files; anything else is an error.

## Current contents
6,559 rows:
- 2,620 LibriSpeech test-clean and 2,939 test-other utterances;
- 843 MUSAN free-sound noises (37 tagged `background`) and 147 MUSAN rfm music tracks;
- 10 synthetic TTS clips (`tts-smoke-01` … `tts-smoke-10`). They are synthetic speech from hexgrad/Kokoro-82M, not recordings of a person, and must never be used to judge or compare models.

## Adding a source
Add a dataset (and any new licence) to `datasets.yaml`, fetch it if it is a download, run `registry build`, check the diff of `sources.csv` and commit both files. A source in a new format needs a new importer in `aqis_lab/registry/importers.py`.
