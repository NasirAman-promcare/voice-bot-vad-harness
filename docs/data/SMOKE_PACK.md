# Smoke pack, version 1 (`data/packs/smoke/v1/`)

Built by WP-0.4 from `packs/specs/smoke_v1.yaml`. It holds 60 clips: 20 LibriSpeech test-clean, 10 LibriSpeech test-other, 10 noisy mixes, 10 non-speech clips and 10 synthetic TTS clips. The pack is for plumbing, cross-machine parity and traceability checks in phase 0. It is not a benchmark.

**The 10 `tts` clips are synthetic speech** (made with hexgrad/Kokoro-82M; see `data/tts_smoke/GENERATION.md`). They are not recordings of a person, and they must never be used to judge or compare models. This replaces the 10 owner recordings of FR-0.4-03 by owner decision (approval `docs/approvals/WP-0.4.md`, plan deviation D6).

## What corpus-v1.tar.gz contains
FR-0.4-02 asks whether the harness corpus `corpus-v1.tar.gz` can supply the smoke pack. It was inspected read-only (listing and its two JSON files); `test_FR_0_4_02_corpus_report_matches_archive` recomputes these facts from the archive.

- sha256 `ef4d5da1e30f6a296f84fb59d38bdb5644a9d3b41ac930b9a3e4e5dae64efbbb`, 46,353,268 bytes, 232 members: the folder `corpus/audio/` with 229 WAV clips, `corpus/manifest.json` and `corpus/build/recipe_log.json`.
- The clips are processed VAD test clips, not source utterances: loudness-normalised (for example −20 dBFS for clean speech), with 200 ms of lead-in and a calibration marker at sample 320.
- The manifest fields are `calibration_marker_offset`, `calibration_marker_offset_samples`, `category`, `clip_id`, `clip_path`, `speech_segments`, `split`, `target_loudness_dbfs` and `target_snr_db`. There are **no transcripts**.
- The recipe log names 229 LibriSpeech FLAC source files from 73 speakers: 38 test-clean speakers, 35 dev-clean speakers and **no test-other speaker**.
- MUSAN appears only as mixing inputs (`musan_noise_floor`, `musan_music` and 117 `speech-us-gov-*` files); no MUSAN noise or music file is in the archive.

Clips per category (file name up to `_dev` or `_test`):

| Category | Clips |
| --- | --- |
| `babble` | 32 |
| `clean_speech` | 30 |
| `loud_clipped` | 18 |
| `music_pure` | 5 |
| `music_speech_mix` | 8 |
| `packet_loss_clean_speech` | 10 |
| `quiet_whisper` | 24 |
| `silence` | 12 |
| `stationary_noise` | 40 |
| `telephony_clean` | 6 |
| `telephony_noisy` | 4 |
| `tier2_seq_babble_5db` | 4 |
| `tier2_seq_clean` | 4 |
| `tier2_seq_stationary_0db` | 4 |
| `tier2_seq_stationary_10db` | 4 |
| `transient_noise` | 24 |

**Conclusion: not usable for the smoke pack** (no transcripts, no test-other, no raw MUSAN noise or music). As the spec requires, the plan asked the owner, who approved downloading the sources from OpenSLR (plan question 1).

## Sources
All downloads come from `www.openslr.org` and are checked against OpenSLR's published MD5 and a SHA-256 pin (`data/registry/datasets.yaml`) before any member is read. Only the subsets listed are extracted, into the git-ignored cache `data/raw/aqis_lab/`. No raw corpus is committed.

| Dataset | Archive | Bytes | Licence | Extracted |
| --- | --- | --- | --- | --- |
| `librispeech-test-clean` | `https://www.openslr.org/resources/12/test-clean.tar.gz` | 346,663,984 | CC BY 4.0 | all 2,620 utterances with transcripts |
| `librispeech-test-other` | `https://www.openslr.org/resources/12/test-other.tar.gz` | 328,757,843 | CC BY 4.0 | all 2,939 utterances with transcripts |
| `musan` | `https://www.openslr.org/resources/17/musan.tar.gz` | 11,086,114,085 | CC BY 4.0 (corpus); per file: see below | `noise/free-sound` (843 files, public domain) and `music/rfm` (147 tracks by Kevin MacLeod, CC BY 3.0, all instrumental) |
| `tts-smoke` | `data/tts_smoke/` in this repository | — | Apache-2.0, attribution to hexgrad/Kokoro-82M | 10 synthetic clips |

- The other MUSAN folders are left out (plan question 2): sound-bible has mixed per-file licences, the other music folders are mostly ShareAlike with irregular licence text, and speech is not needed.
- The pack takes only licences without ShareAlike or NonCommercial terms (`licence_policy` in the spec).
- Fetch everything with `python -m aqis_lab registry fetch all` (about 11.8 GB; 11 min 52 s on the cloud VM), then regenerate the registry with `python -m aqis_lab registry build`. The registry format is in `docs/data/REGISTRY_FORMAT.md`.

## Composition and selection
The spec `packs/specs/smoke_v1.yaml` (pack spec version 1, schema `aqis_lab/packs/schemas/pack_spec.v1.json`) fixes everything; nothing is defaulted. Seed `20260927` was fixed in the plan before any build. `created_utc` is `2026-09-27T00:00:00Z`, written unchanged into the manifest and used as every tar mtime (plan deviation D1).

| Category | Clips | What |
| --- | --- | --- |
| `test-clean` | 20 | LibriSpeech test-clean utterances of 3 to 15 s, one per speaker, taken as they are |
| `test-other` | 10 | LibriSpeech test-other utterances of 3 to 15 s, one per speaker, taken as they are |
| `noisy` | 10 | 10 other test-clean utterances (3 to 15 s, one per speaker) mixed with free-sound noises tagged `background` at 5, 5, 5, 5, 10, 10, 10, 20, 20, 20 dB SNR |
| `non-speech` | 10 | 4 excerpts of 10 s from free-sound noises not tagged `background`, 4 excerpts of 10 s from rfm music, 2 digital silences of 5 s and 10 s |
| `tts` | 10 | all 10 synthetic TTS clips (3 to 8 s each), taken as they are |

Selection rule (`aqis_lab/packs/select.py`):
- For each part of each category, in spec order, the candidates are the registry rows that pass its filter (source, split, tags, duration) and the licence policy and are not yet used anywhere in the pack.
- They are taken in the order of `sha256("aqis-pack-select-v1|<seed>|<category>|<part index>|<role>|<clip_id>")` (hex, ascending), where role is `take`, `mix-speech`, `mix-noise` or `excerpt`, skipping a speaker already taken in the category when the filter asks for distinct speakers.
- Each mix takes the first unused noise clip, in its own key order, that is at least as long as its speech clip.
- Offsets (the noise segment of a mix, an excerpt) are `int(sha256("aqis-pack-offset-v1|<seed>|<derived clip id>|<source clip id>"), 16) mod (source samples − clip samples + 1)`.
- Too few candidates is an error naming the category; nothing depends on registry row order, the clock, `PYTHONHASHSEED` or Python's `random` module.

Clip IDs: clips taken as they are keep their registry `clip_id`. Derived clips are `smoke-mix-NN`, `smoke-noise-NN`, `smoke-music-NN` and `smoke-silence-NN`; the builder refuses a derived ID that is also a registry ID.

Every clip is a canonical 16 kHz mono 16-bit PCM WAV (44-byte header, then the samples). Clips taken as they are keep their samples exactly: FLAC decoding is proven against each file's STREAMINFO MD5, and WAV sources only lose extra chunks such as ffmpeg's `LIST` chunk. A source in another format is an error, never converted.

What the build gives (checked in `EVIDENCE.md`): one mix (`smoke-mix-06`) needed the peak limit, which keeps the SNR; two excerpts (`smoke-music-03`, `smoke-noise-04`) are quiet passages of their sources (about −48 dBFS). No one listens to the clips in this WP, so "non-speech" rests on MUSAN's own labels.

## Recipe v1
Every derived clip's manifest `recipe` is a recipe v1.0 object (schema `aqis_lab/packs/schemas/recipe.v1.json`; plan deviation D2: the pack manifest contract stays at 1.0, where `recipe` is an open object). `pack build` rebuilds every derived clip from its recipe before writing it, and `pack verify` checks every recipe. Clips taken as they are have `recipe: null`.

| Kind | Field | Meaning |
| --- | --- | --- |
| all | `recipe_version` | `"1.0"` |
| all | `kind` | `mix`, `excerpt` or `silence` |
| all | `source_clip_ids` | registry clip IDs used: `[speech, noise]` for a mix, `[source]` for an excerpt, `[]` for silence |
| all | `length_samples` | clip length in samples at 16 kHz |
| mix | `speech_clip_id` | the speech clip (taken whole) |
| mix | `noise_clip_id` | the noise clip |
| mix | `snr_db` | target SNR in dB, as written in the spec |
| mix | `seed` | the pack seed the noise offset was derived from |
| mix | `noise_offset_samples` | first sample of the noise segment |
| mix | `snr_definition` | the definition below, word for word |
| mix | `speech_gain` | `speech_gain_q24 / 2^24` (1.0 unless the peak limit applied) |
| mix | `noise_gain` | `noise_gain_q24 / 2^24` |
| mix | `speech_gain_q24` | speech gain as an integer with 24 fractional bits |
| mix | `noise_gain_q24` | noise gain as an integer with 24 fractional bits |
| mix | `peak_limited` | whether both gains were scaled down together to stay in the 16-bit range |
| mix | `achieved_snr_db` | SNR given by the quantised gains, rounded to 4 decimals |
| excerpt | `seed` | the pack seed the offset was derived from |
| excerpt | `offset_samples` | first sample of the excerpt in its source |

SNR definition: SNR = 10*log10(Ps/Pn), where Ps and Pn are the mean squares of the 16-bit sample values of the whole speech clip and of the equally long noise segment, each multiplied by its gain

Arithmetic (`aqis_lab/packs/mix.py`), the same on every machine:
- The sums of squares `Ss` and `Sn` are exact integers.
- The noise gain `g = sqrt(Ss / (Sn * 10^(SNR/10)))` is computed with Python's `decimal` module at 50 digits (`exp`, `ln` and `sqrt` are correctly rounded there) and rounded half-even to `noise_gain_q24 = round(g * 2^24)`.
- Each mixed sample is `(s * speech_gain_q24 + n * noise_gain_q24 + 2^23) >> 24` in 64-bit integers.
- If a sample would leave −32768..32767, both gains are multiplied by `32767 * 2^24 / peak` (rounded down), which keeps the SNR, and `peak_limited` is true.
- A silent speech clip or noise segment is an error.

## Layout
Drive-friendly limits (FR-0.4-06), enforced by `pack build` and `pack verify`:
- **At most 1,000 entries (files and subfolders) in any folder**: the pack folder, and every folder inside the archives once extracted.
- **At most 200,000,000 bytes per archive** (the stricter reading of 200 MB), counting the whole tar file.
- A spec may set lower limits, never higher.

Pack folder `data/packs/<manifest_id>/v<major>/`:
- `manifest.json`: the pack manifest (contract `docs/contracts/PACK_MANIFEST.md`), UTF-8 JSON with sorted keys, 2-space indent and a final newline.
- `LICENCES.md`: every source with its licence and attribution, and every clip's licence.
- `build_record.json`: the SHA-256 and names of the pack spec, registry and datasets file, the seed, the builder version and the manifest's canonical SHA-256 (plan deviation D5). It holds no time or git commit.
- Archives named `<manifest_id>-<version>-<category>-<nnn>.tar`, one or more per category, for example `smoke-1.0.0-noisy-000.tar`.

Archives:
- Uncompressed USTAR tar. Every member is a regular file with mode 0644, uid and gid 0, empty user and group names and mtime = `created_utc`; there are no folder entries.
- Members are ordered by `clip_id`; archives follow the spec's category order; a category moves to a new archive before the size limit.
- Member path `<category>/<clip_id>.wav`, or `<category>/<nnn>/<clip_id>.wav` (numbered subfolders of at most 1,000 clips) when a category has more than 1,000 clips.
- A single clip too large for one archive is an error.

The smoke pack: 5 archives, 12.6 MB in total.

## Build and verify
- Build: `python -m aqis_lab pack build packs/specs/smoke_v1.yaml --out data/packs/smoke/v1`. It needs the fetched sources and `data/registry/sources.csv`, never overwrites a folder, and writes through a staging folder. Measured on the cloud VM: 0.68 s (NFR-0.4-01 allows 2 minutes; fetching the sources is separate).
- Verify: `python -m aqis_lab pack verify data/packs/smoke/v1` needs no sources and no network. It prints `pack smoke 1.0.0: OK, 60 clips in 5 archives; test-clean 20, test-other 10, noisy 10, non-speech 10, tts 10`.
- Building twice gives byte-identical files (AT-0.4-01; `test_FR_0_4_05_build_twice_byte_identical`).
