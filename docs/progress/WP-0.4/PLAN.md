# PLAN — WP-0.4 Source registry, pack builder and smoke pack

Spec: `docs/specs/phase-0/WP-0.4-registry-packs.md`  ·  Planned by session: https://claude.ai/code/session_01PXSpYQ1gMgEWyKcQ63tXga  ·  Date: 2026-09-27
Branch: `claude/optimistic-ptolemy-tdbotx`  ·  Base: `origin/main` at `a637a15`  ·  Depends on: WP-0.0 and WP-0.2 (both MERGED in `docs/progress/STATUS.md`)

## Summary
When this WP is done, every test clip in the lab can be traced to where it came from and under what licence, and packs are built the same way every time.
- **Registry.** `data/registry/sources.csv` lists every source clip the lab has acquired: all LibriSpeech test-clean and test-other utterances, two MUSAN subsets, and the owner's recordings. Each row has its licence, speaker, consent reference, transcript, split and file hash. `docs/data/REGISTRY_FORMAT.md` documents the format. Validation rejects a missing or unknown licence and an owner recording without a consent reference that resolves.
- **Acquisition.** `aqis_lab/registry/` downloads the public archives from OpenSLR, checks each archive's hash before using it, and extracts only the subsets the registry uses into a git-ignored cache (`data/raw/aqis_lab/`). No raw corpus is committed.
- **Pack builder.** `python -m aqis_lab pack build <spec> --out <dir>` selects clips by seeded rules, writes 16 kHz mono 16-bit PCM WAV clips, mixes noisy clips with integer arithmetic, and writes normalised tar shards, a manifest valid under the WP-0.2 contract, and `LICENCES.md`. The same inputs always give byte-identical files. `python -m aqis_lab pack verify <dir>` recomputes every hash and checks every archive member, every manifest entry and the folder and archive size limits.
- **Smoke pack.** `packs/specs/smoke_v1.yaml` and the built pack in `data/packs/smoke/v1/`: exactly 20 test-clean, 10 test-other, 10 noisy mixes (5, 10 and 20 dB SNR), 10 non-speech clips and 10 owner recordings. `docs/data/SMOKE_PACK.md` reports what `corpus-v1.tar.gz` contains, the sources, the selection and mixing rules, the layout and how to rebuild and verify.

## What I found in the repository and environment (read-only inspection)
1. **Spec sources.** "Read first" names the Build Plan sections "Dataset architecture" and "Phase 0". The Build Plan is not in the repository. As in WP-0.2 and WP-0.3 (your instruction that `docs/specs/phase-0/` is authoritative and self-contained), this plan relies on the spec, the Phase 0 overview conventions, the pack manifest contract (`docs/contracts/PACK_MANIFEST.md`) and the specs that use packs (WP-0.5 copies archives and runs shards, WP-0.6 traces rows to a manifest version, WP-0.7 runs the smoke pack). `aqis-kit-patch-3/docs/specs/phase-0/WP-0.4-registry-packs.md` is byte-identical to the spec (`diff`, no output).
2. **`corpus-v1.tar.gz` cannot supply the smoke pack (FR-0.4-02).** I listed it and read its two JSON files without extracting anything into the repository:
   - sha256 `ef4d5da1…fbbb`, 46,353,268 bytes (the WP-0.0 pin); 232 members: `corpus/audio/` with 229 WAV clips, `corpus/manifest.json` and `corpus/build/recipe_log.json`.
   - The 229 clips are **processed VAD test clips**, not source utterances. They fall into 16 categories (for example babble 32, clean_speech 30, stationary_noise 40, quiet_whisper 24, silence 12, music_pure 5). The clean speech clips are loudness-normalised to −20 dBFS, have 200 ms of lead-in and a calibration marker at sample 320.
   - **No transcripts.** The manifest fields are `clip_id`, `category`, `split` (dev/test), `speech_segments`, `target_snr_db`, `target_loudness_dbfs` and calibration offsets.
   - **No test-other.** The recipe log names 229 LibriSpeech FLAC sources from 73 speakers: 38 are test-clean speakers, 35 are dev-clean speakers, and none is a test-other speaker (checked against the speaker folders of the real test-clean and test-other archives).
   - **No raw MUSAN audio.** MUSAN appears only as mixing inputs (`musan_noise_floor`, `musan_music`, 117 `speech-us-gov-*` files); no noise or music file is in the archive.

   So the spec's condition "use it if it holds the needed LibriSpeech test-clean and test-other utterances with transcripts and MUSAN noise and music" is not met. The spec says to stop and ask with download options: that is question 1. `docs/data/SMOKE_PACK.md` will carry this report.
3. **Download hosts** (HEAD requests and short range downloads, nothing stored in the repository):
   - `www.openslr.org` is **reachable**, 15 to 17 MB/s, and supports HTTP range requests (206 answers):
     - LibriSpeech (SLR12, CC BY 4.0): `test-clean.tar.gz` 346,663,984 bytes and `test-other.tar.gz` 328,757,843 bytes;
     - MUSAN (SLR17, CC BY 4.0 as a corpus): `musan.tar.gz` 11,086,114,085 bytes.
   - The mirrors `openslr.elda.org`, `openslr.trmal.net` and `openslr.magicdatatech.com` answer **403** from the session proxy. `us.openslr.org` connected but did not answer the HEAD request in 25 s.
   - Published checksums: OpenSLR's `md5sum.txt` (test-clean `32fa31d2…f9a9`, test-other `fb5a5037…3135`) and MUSAN's `checksum.md5` (`musan.tar.gz` `0c472d4f…df`).
   - I downloaded both LibriSpeech archives into the scratchpad: both MD5s match the published values. SHA-256: test-clean `39fde525e59672dc6d1551919b1478f724438a95aa55f874b576be21967e6c23`, test-other `d09c181bba5cf717b3dee7d4d592af11a3ee3a09e08ae025c5506f6ebe961c29`.
4. **LibriSpeech contents** (measured from the real archives):
   - test-clean: 2,620 utterances, 40 speakers. test-other: 2,939 utterances, 33 speakers. Every utterance has a transcript line in its chapter's `*.trans.txt` (upper case, no punctuation).
   - All FLAC files are 16 kHz, mono, 16-bit. Every STREAMINFO block carries the encoder's MD5 of the audio samples.
   - Durations: 1.25 s to 34.95 s, median 5.79 s (clean) and 5.15 s (other). Between 3 and 15 s: 1,991 (clean) and 2,256 (other).
   - `LibriSpeech/LICENSE.TXT` reads "LibriSpeech (c) 2014 by Vassil Panayotov. LibriSpeech ASR corpus is licensed under a Creative Commons Attribution 4.0 International License."
5. **MUSAN contents and licences** (I streamed the whole archive once and kept only its README, LICENSE and ANNOTATIONS files, in the scratchpad):
   - Every file is 16 kHz, mono, 16-bit PCM WAV (checked on the first music files; the build checks every file).
   - The README says each subfolder's LICENSE file "connects the individual files … to the governing license", and that all files are under a Creative Commons licence or in the US public domain, with nothing that forbids commercial use.
   - **The licences differ by subfolder and by file:**
     - `noise/free-sound` (about 846 files; the noise README gives 932 noise recordings, 86 of them in sound-bible): its LICENSE says all recordings were marked **Public Domain** on Freesound. Its ANNOTATIONS lists 37 "Background noises" (ambient recordings).
     - `noise/sound-bible` (86 files): a mix of "Attribution 3.0" and "Public Domain", per file.
     - `music/rfm` (147 tracks): all by Kevin MacLeod (incompetech.com), all **CC BY 3.0**, all instrumental (vocals `N`). Its LICENSE gives the title of every track, so attribution text can be generated for each one.
     - `music/fma`, `fma-western-art`, `hd-classical`, `jamendo`: per-file licences from CC BY 3.0 and 4.0 to **ShareAlike** variants (CC BY-SA 1.0, 2.5, 3.0, 3.0 US, 4.0), written in irregular free text (for example "Attribution-ShareAlike 4.0 Unported (CC BY-SA 3.0)"). Many tracks have vocals.
   - A ShareAlike source would oblige every derived clip (an excerpt or a mix) to carry that ShareAlike licence. This is question 2.
6. **Decoding FLAC.** The lab lock has no audio library. In a scratch environment, `soundfile 0.14.0` (bundling libsndfile 1.2.2) decoded 300 test-clean utterances; for **all 300**, the MD5 of the decoded samples equals the MD5 stored in the FLAC file by its encoder. So decoding can be proven exact on every machine, independently of the decoder. `soundfile` has wheels for x86_64 and aarch64 glibc Linux (manylinux_2_28) and needs `numpy` and `cffi` (question 8).
7. **Lock trial.** In the scratchpad, `uv pip compile` with the recorded command and `soundfile` and `numpy` added resolved for 3.13 on both architectures. Every existing pin stayed at its version. New pins: `cffi 2.1.1`, `numpy 2.5.3`, `pycparser 3.0`, `soundfile 0.14.0`, `typing-extensions 4.16.0`.
8. **Pack manifest contract (WP-0.2).**
   - `created_utc` is required ("when the manifest was written"). A wall-clock value would make two builds differ, which AT-0.4-01 forbids (question 5).
   - `recipe` is an open object in v1.0. `PACK_MANIFEST.md` says its members "are fixed in a later minor version (WP-0.4 FR-0.4-04)". A contract bump to 1.1 would break three existing WP-0.2 tests (question 6).
   - `consent_ref` is required for clips whose `source` is `owner` or `campaign` (WP-0.2 question 4), so owner recordings use `source: owner`.
9. **Repository fit.**
   - The root `.gitignore` (GUARDED) already ignores `/data/raw/`. So the source cache under `data/raw/aqis_lab/` needs no `.gitignore` change.
   - `data/`, `packs/` and `docs/data/` do not exist yet and are not protected paths.
   - The CLI dispatcher (`aqis_lab/__main__.py`, `COMMANDS`) needs new entries.
   - `data/owner_smoke/` does not exist: the owner recordings are missing (owner need 2).
   - The repository is private (GitHub reports `visibility: private`).
10. **Machine.** The cloud VM has 4 CPUs, 15 GB RAM and 30 GB free disk. Keeping the MUSAN archive and the extracted subsets needs about 14 GB (see "Measurements").
11. **Environment probes.** `docs/environment/oracle_probe.txt` is missing. This WP runs on the cloud VM only, so it is not needed now (risk 6).

## Amendment after approval: synthetic TTS clips instead of owner recordings (deviation D6)
Owner decision in `docs/approvals/WP-0.4.md` on `main` (`655b4e1`): there are no owner recordings in phase 0. The approval's conditions override the rest of this plan wherever they differ. What changes:
- **Category and source.** The fifth smoke category is `tts`, not `owner`. Its 10 clips come from `data/tts_smoke/` (`01.wav` … `10.wav`, `transcripts.csv`, `GENERATION.md`). These are synthetic speech made with hexgrad/Kokoro-82M (kokoro 0.9.4, voices `af_heart`, `am_michael`, `bf_emma`, `bm_george`), as recorded in `GENERATION.md`. No person was recorded.
- **Registry rows.** Dataset `tts-smoke` (a local folder, no download). Each row has:
  - `clip_id` `tts-smoke-<stem>`, `source` `tts`, `split` `tts`, `source_ref` `data/tts_smoke/<file>`;
  - `speaker_id` `kokoro-<voice>`, from the Voice column of `GENERATION.md`;
  - `consent_ref` empty (no consent is needed: no person was recorded);
  - `licence` `Apache-2.0`, with attribution to hexgrad/Kokoro-82M;
  - `transcript` the exact TTS input text from `transcripts.csv`;
  - `tags` `synthetic`, `tts` and `voice-<voice>`.
- **Import checks.**
  - The importer checks `transcripts.csv` against the WAV files one to one, and against the Text column of `GENERATION.md`.
  - It checks each file's SHA-256 against the `GENERATION.md` table (all 10 match today) and requires 16 kHz mono 16-bit PCM.
  - Any mismatch is an error, never corrected.
- **Pack.** Category `tts`: all 10 `tts` rows, 3 to 8 s each (measured: 4.15 to 5.40 s). They are taken as they are (`recipe: null`) and rewritten with a canonical WAV header, which drops ffmpeg's `LIST` chunk. Manifest `licence` is `Apache-2.0`, `consent_ref` is null, and `tags` include `synthetic`. The shard is `smoke-1.0.0-tts-000.tar`. The `pack verify` report ends with `test-clean 20, test-other 10, noisy 10, non-speech 10, tts 10`.
- **Licences.** `LICENCES.md` has an Apache-2.0 section: licence name and link (`https://www.apache.org/licenses/LICENSE-2.0`), attribution to hexgrad/Kokoro-82M (`https://huggingface.co/hexgrad/Kokoro-82M`) and the kokoro package version, and "changes made" (0.4 s of silence at each end, converted to 16 kHz mono 16-bit PCM, WAV header rewritten).
- **Wording.** Every document and report (`REGISTRY_FORMAT.md`, `SMOKE_PACK.md`, `LICENCES.md`, `EVIDENCE.md`) calls these clips synthetic, never recordings. `SMOKE_PACK.md` states that they must never be used to judge or compare models.
- **Owner-recording and consent code kept.**
  - The owner import (`data/owner_smoke/`-style folder with `CONSENT.md`) and the consent rules (`owner` and `campaign` rows need a `consent_ref` that resolves) stay in the code for the Phase 1 campaign recordings.
  - Their tests use generated test inputs only.
  - No owner recordings are committed in phase 0, `datasets.yaml` has no owner dataset, and question 4 does not apply.
- **Tests changed by this amendment.**
  - `test_FR_0_4_03_owner_clips_need_3_to_8_seconds` becomes `test_FR_0_4_03_tts_clips_need_3_to_8_seconds`.
  - `test_FR_0_4_07_owner_recordings_name_consent_ref` stays (generated owner inputs).
  - `test_FR_0_4_07_synthetic_clips_attributed_under_apache_2` is new.
  - `test_FR_0_4_01_tts_rows_match_generation_record` is new: rows against `GENERATION.md`, with hashes and texts recomputed in the test.
  - `test_FR_0_4_01_committed_registry_row_counts` expects 10 `tts` rows and 0 `owner` rows.
  - The smoke spec and count tests expect `tts` 10.
- **Owner need 2** (owner recordings) is withdrawn. Nothing else is needed from the owner to build.

## Requirements
| Requirement | Approach | New files | Changed files and functions (change budget) | Tests | Acceptance command |
| --- | --- | --- | --- | --- | --- |
| FR-0.4-01 | Registry CSV with the spec's fields plus the columns listed under "Registry" below. `registry build` generates it deterministically from the fetched datasets and `data/owner_smoke/`. `validate_registry` reports every problem by row and column, never only the first. Rules: `licence` must be present and defined in the licence table of `datasets.yaml`; `owner` and `campaign` rows need a `consent_ref` that names an existing, non-empty file in the repository; speech rows need a transcript and a speaker; non-speech rows have neither; `clip_id` valid and unique; file facts (hash, rate, channels, samples) well formed. Owner import checks format, file names and that `transcripts.csv` matches the WAV files one to one | `aqis_lab/registry/__init__.py`, `registry.py`, `datasets.py`, `importers.py`, `aqis_lab/commands/registry.py`, `data/registry/sources.csv`, `data/registry/datasets.yaml`, `docs/data/REGISTRY_FORMAT.md` | `aqis_lab/__main__.py`: `COMMANDS` (one entry) and the CHANGE LOG (one line) | `test_FR_0_4_01_registry_has_spec_columns`, `test_FR_0_4_01_rejects_missing_licence`, `test_FR_0_4_01_rejects_unknown_licence`, `test_FR_0_4_01_rejects_owner_row_without_consent`, `test_FR_0_4_01_rejects_consent_ref_that_does_not_resolve`, `test_FR_0_4_01_rejects_speech_row_without_transcript_or_speaker`, `test_FR_0_4_01_rejects_non_speech_row_with_transcript`, `test_FR_0_4_01_rejects_invalid_or_duplicate_clip_id`, `test_FR_0_4_01_reports_every_problem_by_row_and_column`, `test_FR_0_4_01_build_is_deterministic` (shuffled input order, other `PYTHONHASHSEED`: byte-identical CSV), `test_FR_0_4_01_librispeech_rows_from_archive` (generated LibriSpeech-shaped archive), `test_FR_0_4_01_musan_rows_carry_subset_licence_and_titles`, `test_FR_0_4_01_owner_import_rejects_bad_inputs` (missing or extra transcript, empty text, wrong format, bad file name, missing `CONSENT.md`), `test_FR_0_4_01_committed_registry_is_valid`, `test_FR_0_4_01_committed_registry_row_counts` (2,620 test-clean and 2,939 test-other from the LibriSpeech paper; 147 rfm from MUSAN's ANNOTATIONS; 10 owner), `test_FR_0_4_01_format_doc_lists_every_column`, `test_FR_0_4_01_cli_validate_exit_codes` | AT-0.4-03 |
| FR-0.4-02 | Report of `corpus-v1.tar.gz` in `SMOKE_PACK.md` (finding 2). `registry fetch <dataset>`: resumable HTTP download (range requests) into the cache, then byte count, pinned SHA-256 and published MD5 checked **before** any member is read; a mismatch deletes the download and exits 2. Only the members matching the dataset's extract patterns are written, and only regular files with safe relative paths (no links, no absolute or `..` paths). A completion marker lists every extracted file with its SHA-256. A second fetch downloads nothing. Nothing is written outside the cache, and the cache must be git-ignored | `aqis_lab/registry/fetch.py`, `docs/data/SMOKE_PACK.md` | none | `test_FR_0_4_02_fetch_checks_hash_before_extracting` (real HTTP from a local server in the test), `test_FR_0_4_02_fetch_rejects_wrong_hash_and_keeps_nothing`, `test_FR_0_4_02_fetch_resumes_partial_download`, `test_FR_0_4_02_second_fetch_downloads_nothing`, `test_FR_0_4_02_extracts_only_listed_members_safely` (absolute, `..`, symlink and hard-link members rejected), `test_FR_0_4_02_refuses_cache_not_ignored_by_git`, `test_FR_0_4_02_corpus_report_matches_archive` (counts recomputed in the test from `corpus-v1.tar.gz`), `test_FR_0_4_02_no_raw_corpus_committed` (`git ls-files`: nothing under `data/raw/`, audio only in `data/packs/` and `data/owner_smoke/`), `test_FR_0_4_02_dataset_pins_match_openslr` (marked `slow` and `network`: fetches the three archives and checks the pins) | AT-0.4-01 |
| FR-0.4-03 | Pack spec (`packs/specs/smoke_v1.yaml`, validated against `aqis_lab/packs/schemas/pack_spec.v1.json`) declares the five categories, their counts, filters, SNRs and seed (question 7). The selection rule under "Selection" below is independent of registry row order and of Python's `random`. The builder fails, naming the category, when there are too few candidates. Every clip is written as a canonical 16 kHz mono 16-bit PCM WAV. Sources that are not in that format are rejected, never converted (question 3) | `aqis_lab/packs/__init__.py`, `spec.py`, `select.py`, `audio.py`, `schemas/pack_spec.v1.json`, `packs/specs/smoke_v1.yaml` | none | `test_FR_0_4_03_smoke_spec_declares_exact_composition` (spec read in the test: 20/10/10/10/10, SNRs 5, 10 and 20 only, non-speech kinds noise, music and silence), `test_FR_0_4_03_builder_selects_exact_counts`, `test_FR_0_4_03_fails_when_too_few_candidates`, `test_FR_0_4_03_selection_ignores_registry_row_order`, `test_FR_0_4_03_selection_changes_with_seed`, `test_FR_0_4_03_distinct_speakers_and_utterances`, `test_FR_0_4_03_all_clips_16k_mono_pcm16` (WAV headers parsed in the test with `wave`), `test_FR_0_4_03_flac_decode_checked_against_streaminfo_md5`, `test_FR_0_4_03_rejects_source_in_other_format`, `test_FR_0_4_03_tts_clips_need_3_to_8_seconds`, `test_FR_0_4_03_committed_smoke_pack_has_exact_counts` (committed manifest and archives, counted in the test) | AT-0.4-02 |
| FR-0.4-04 | Integer mixing with gains computed in `decimal` (pure software, the same on every CPU), quantised to 24 fractional bits, and one common scale factor if the mix would clip. The noise offset is derived from the seed with SHA-256. Recipe v1 (see "Recipes") records the source clip IDs, SNR, seed, offset, gains (exact values and their integer forms) and whether the peak was limited. `render_clip(recipe, sources)` rebuilds a derived clip from its recipe alone | `aqis_lab/packs/mix.py`, `schemas/recipe.v1.json` | none | `test_FR_0_4_04_same_inputs_and_seed_byte_identical`, `test_FR_0_4_04_different_seed_changes_audio`, `test_FR_0_4_04_recipe_records_sources_snr_seed_gains` (schema and values), `test_FR_0_4_04_clip_rebuilt_from_recipe_alone`, `test_FR_0_4_04_snr_matches_definition` (SNR recomputed in the test from the output with `fractions`; within 0.01 dB), `test_FR_0_4_04_gains_equal_independent_decimal_computation`, `test_FR_0_4_04_peak_limit_keeps_snr_and_is_recorded`, `test_FR_0_4_04_rejects_noise_shorter_than_speech`, `test_FR_0_4_04_recipe_doc_matches_schema` | AT-0.4-01 |
| FR-0.4-05 | `pack build`: validate spec and registry, check every used source file against its registry SHA-256, render clips, write per-category tar shards with normalised headers in a fixed order, write `manifest.json` (validated with `validate_manifest` before it is written), `LICENCES.md` and `build_record.json`. Everything goes into a staging folder that is renamed into place at the end; an existing `--out` folder is never overwritten. `pack verify`: see "Verify" below; it reports every problem and exits 1 on any | `aqis_lab/packs/archive.py`, `build.py`, `verify.py`, `aqis_lab/commands/pack.py`, `data/packs/smoke/v1/` (manifest, shards, `LICENCES.md`, `build_record.json`) | `aqis_lab/__main__.py`: `COMMANDS` (one entry) and the CHANGE LOG (one line) | `test_FR_0_4_05_manifest_valid_under_wp_0_2_schema`, `test_FR_0_4_05_archive_hashes_sizes_and_member_counts_recorded`, `test_FR_0_4_05_members_in_documented_order`, `test_FR_0_4_05_tar_headers_are_normalised`, `test_FR_0_4_05_build_twice_byte_identical` (different working folder, `PYTHONHASHSEED`, `TZ`, `umask` and registry row order), `test_FR_0_4_05_created_utc_comes_from_spec`, `test_FR_0_4_05_verify_passes_on_built_pack`, `test_FR_0_4_05_verify_fails_on_changed_member`, `test_FR_0_4_05_verify_fails_on_missing_member`, `test_FR_0_4_05_verify_fails_on_extra_member`, `test_FR_0_4_05_verify_fails_on_changed_or_missing_archive`, `test_FR_0_4_05_verify_fails_on_extra_file_in_pack_folder`, `test_FR_0_4_05_verify_fails_on_manifest_entry_mismatch` (hash, duration, rate, channels, member path, archive name), `test_FR_0_4_05_verify_rejects_unsafe_member`, `test_FR_0_4_05_verify_reports_every_problem`, `test_FR_0_4_05_build_refuses_existing_output`, `test_FR_0_4_05_failed_build_leaves_nothing`, `test_FR_0_4_05_build_rejects_source_with_wrong_hash`, `test_FR_0_4_05_cli_exit_codes`, `test_FR_0_4_05_pack_and_registry_listed_by_dispatcher`, `test_FR_0_4_05_committed_smoke_pack_verifies`, `test_FR_0_4_05_build_record_traces_inputs` (only if D5 is accepted), `test_FR_0_4_05_rebuild_equals_committed_smoke_pack` (marked `slow` and `network`) | AT-0.4-01, AT-0.4-02 |
| FR-0.4-06 | Hard limits `MAX_FILES_PER_FOLDER = 1000` (entries in any folder: the pack folder and every folder inside the archives) and `MAX_ARCHIVE_BYTES = 200,000,000` (whole tar file, headers and padding included). A spec may set lower limits, never higher. The builder computes each tar's exact size before writing it, starts a new shard before the limit, and puts clips into numbered subfolders when a category has more than the folder limit. A single clip too large for one archive is an error. `pack verify` enforces both limits too | (in `archive.py`, `build.py`, `verify.py`, `SMOKE_PACK.md` "Layout") | none | `test_FR_0_4_06_splits_archives_at_size_limit` (exact byte sizes checked in the test), `test_FR_0_4_06_splits_member_folders_at_1000_files` (1,001 generated clips with the real limit), `test_FR_0_4_06_rejects_limits_above_hard_caps`, `test_FR_0_4_06_rejects_clip_larger_than_archive_limit`, `test_FR_0_4_06_verify_fails_on_oversized_archive`, `test_FR_0_4_06_verify_fails_on_crowded_folder`, `test_FR_0_4_06_layout_doc_states_the_limits` | AT-0.4-02 |
| FR-0.4-07 | `LICENCES.md` is generated from the registry, `datasets.yaml` and the manifest; it contains no timestamps. It has one section per source with the licence name and link and the full attribution text: creator, title or source name, copyright notice where given, licence notice and link, link to the material, and "changes made". For MUSAN music there is one attribution line per track used; owner recordings carry their consent reference. A table maps every clip to its source file and licence. `pack verify` checks that every manifest clip and licence appears in it | `aqis_lab/packs/licences.py` | none | `test_FR_0_4_07_lists_every_source_and_licence`, `test_FR_0_4_07_cc_by_attribution_has_required_elements` (elements listed in the test from the CC BY 3.0 and 4.0 legal code, section 3), `test_FR_0_4_07_music_tracks_attributed_individually`, `test_FR_0_4_07_owner_recordings_name_consent_ref`, `test_FR_0_4_07_generated_deterministically`, `test_FR_0_4_07_verify_fails_when_a_clip_is_missing`, `test_FR_0_4_07_committed_licences_cover_committed_manifest` | AT-0.4-02 |
| NFR-0.4-01 | The build reads each used source file once, decodes only the 40 LibriSpeech utterances and reads WAV excerpts by seeking. Measured with the real sources on the cloud VM (planning estimate: well under 20 s). Fetching sources is a separate step and is not part of the build time | — | none | `test_NFR_0_4_01_smoke_build_under_2_minutes` (marked `slow` and `network`: fetches the sources if the cache lacks them, then times only `pack build` with a monotonic clock) | `rm -rf /tmp/wp04-time && time .venv/bin/python -m aqis_lab pack build packs/specs/smoke_v1.yaml --out /tmp/wp04-time` (bash `time`; `real` under 2m0s) |
| AT-0.4-01 | Run as written | — | — | `test_FR_0_4_05_build_twice_byte_identical`, `test_FR_0_4_05_rebuild_equals_committed_smoke_pack` | `rm -rf /tmp/wp04-a /tmp/wp04-b && .venv/bin/python -m aqis_lab pack build packs/specs/smoke_v1.yaml --out /tmp/wp04-a && .venv/bin/python -m aqis_lab pack build packs/specs/smoke_v1.yaml --out /tmp/wp04-b && (cd /tmp/wp04-a && sha256sum *) > /tmp/wp04-a.sha && (cd /tmp/wp04-b && sha256sum *) > /tmp/wp04-b.sha && diff /tmp/wp04-a.sha /tmp/wp04-b.sha && diff -r /tmp/wp04-a data/packs/smoke/v1` (no output; exit 0) |
| AT-0.4-02 | Run as written | — | — | `test_FR_0_4_05_committed_smoke_pack_verifies`, `test_FR_0_4_03_committed_smoke_pack_has_exact_counts` | `.venv/bin/python -m aqis_lab pack verify data/packs/smoke/v1` (exit 0; the report prints `test-clean 20, test-other 10, noisy 10, non-speech 10, tts 10`; amended by D6) |
| AT-0.4-03 | Run as written after `git fetch origin main` | — | — | — | `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.4` |

**Change budget for existing files** (nothing else that already exists is touched):
- `aqis_lab/__main__.py`: add the `"pack"` and `"registry"` entries to `COMMANDS` and two CHANGE LOG lines to the module docstring. `build_parser` and `main` stay byte-identical. CAP-CLI-001's behaviour is unchanged, so its registry row stays as it is.
- `requirements/aqis_lab/phase0.in` (LAB-OWNED): append one commented block with `soundfile` and `numpy` (question 8). Existing lines stay byte-identical.
- `requirements/aqis_lab/phase0.txt` (LAB-OWNED): regenerated only with the command recorded in its header. Existing pins must stay unchanged; the build checks this with `git diff`.
- `docs/contracts/PACK_MANIFEST.md` (only if question 6 (a) is accepted): the "Meaning" cell of the `/clips/*/recipe` row only. It will say that the members are defined by recipe v1 in `docs/data/SMOKE_PACK.md` and checked by `pack build` and `pack verify`, and that the manifest schema keeps `recipe` open. The field table's paths and types, which `test_FR_0_2_07_documents_and_schemas_list_same_fields` compares, do not change.
- `docs/capabilities/REGISTRY.md`:
  - append new rows;
  - in the CAP-ENV-002 row, update only the "What it does" cell so it names the added packages;
  - all other rows stay byte-identical.
- `docs/progress/STATUS.md`: the WP-0.4 row only. `docs/progress/BLOCKERS.md`: append-only, and only if I get blocked. `docs/progress/DEBT.md`: rows only if an audit finding is accepted as debt.
- No GUARDED or NEVER path changes, so no `ALLOW-EDIT` is needed. No existing test file changes.

**New files** (besides those in the table):
- `docs/progress/WP-0.4/EVIDENCE.md`.
- Test modules (the `test_aqis_` prefix keeps basenames unique, FR-0.0-04):
  - `tests/aqis_lab/test_aqis_registry_validate.py`, `test_aqis_registry_build.py`, `test_aqis_registry_fetch.py`;
  - `test_aqis_packs_select.py`, `test_aqis_packs_mix.py`, `test_aqis_packs_build.py`, `test_aqis_packs_verify.py`, `test_aqis_packs_layout.py`, `test_aqis_packs_licences.py`, `test_aqis_packs_smoke.py` (committed registry and pack, and the `slow`/`network` tests);
  - helper `tests/aqis_lab/aqis_packs_testutil.py`. At test time it writes small source archives shaped like LibriSpeech and MUSAN (generated tones and seeded noise, FLAC and WAV, with LICENSE and ANNOTATIONS files in MUSAN's format) and an owner folder, all into `tmp_path`, and serves them over HTTP from `127.0.0.1`. No audio fixture is committed; the helper's signals are test inputs only, never pack content.
- Registry rows, all ACTIVE and introduced by WP-0.4:
  - CAP-REG-001: registry reading, writing and validation (`registry.py`);
  - CAP-REG-002: dataset and licence definitions (`datasets.py`, `data/registry/datasets.yaml`);
  - CAP-REG-003: acquisition (`fetch.py`);
  - CAP-REG-004: registry import from datasets and owner recordings (`importers.py`);
  - CAP-REG-005: the `registry` command (`commands/registry.py`);
  - CAP-PACK-001: pack spec loading and seeded selection (`spec.py`, `select.py`);
  - CAP-PACK-002: canonical WAV writing and exact FLAC decoding (`audio.py`);
  - CAP-PACK-003: mixing, excerpts, silence and recipe v1 (`mix.py`);
  - CAP-PACK-004: normalised tar shards and the layout limits (`archive.py`);
  - CAP-PACK-005: `pack build` (`build.py`);
  - CAP-PACK-006: `pack verify` (`verify.py`);
  - CAP-PACK-007: `LICENCES.md` generation (`licences.py`);
  - CAP-PACK-008: the `pack` command (`commands/pack.py`);
  - CAP-DATA-001: the committed registry `data/registry/sources.csv`;
  - CAP-DATA-002: the committed smoke pack `data/packs/smoke/v1/`;
  - CAP-DOC-007: `REGISTRY_FORMAT.md`;
  - CAP-DOC-008: `SMOKE_PACK.md`.

## Design details
Rows marked **question** need your answer. Everything else is a design decision that approving the plan accepts; tell me to change any of it.

### Datasets and licences (`data/registry/datasets.yaml`, addition D4)
- One entry per dataset:
  - `librispeech-test-clean` and `librispeech-test-other`: URL, bytes, SHA-256 pin, published MD5, extract patterns (`LibriSpeech/<split>/**` and the top-level `*.TXT` files);
  - `musan`: the same fields, with extract patterns `musan/README`, `musan/noise/README`, `musan/music/README`, `musan/noise/free-sound/**` and `musan/music/rfm/**` (question 2);
  - `owner-smoke`: the folder `data/owner_smoke`, no download.
- **Pins**: the LibriSpeech pins are the values in finding 3. For MUSAN, the build first checks the published MD5 and then records the SHA-256 in the file; the planning stream gave `86d1061c7e15b5c9e906777685c519701df51bfde3001e1070dcc9ffac955ee1`, which the build confirms before it is pinned.
- **Subset licence files are pinned too**: `musan/noise/free-sound/LICENSE` sha256 `29766529…672d`, `musan/music/rfm/LICENSE` `85cce3e3…c423`. If either file differs, the registry build stops instead of guessing a licence.
- **Licence table**: each licence has an ID (SPDX where one exists), a name, a URL, whether attribution is required, and whether it has ShareAlike or NonCommercial terms. Entries:
  - `CC-BY-4.0` (LibriSpeech, and the MUSAN corpus as a whole);
  - `CC-BY-3.0` (rfm tracks);
  - `LicenseRef-public-domain` (free-sound: "marked as in the Public Domain on Free Sound");
  - `CC0-1.0` (silence generated by the lab; question 3);
  - the owner-recording licence (question 3).
- **Attribution templates** per dataset, quoted from the sources: LibriSpeech's `LICENSE.TXT` and OpenSLR page; MUSAN's README citation and OpenSLR page; for rfm, incompetech's form, `"<Title>" Kevin MacLeod (incompetech.com), Licensed under Creative Commons: By Attribution 3.0, http://creativecommons.org/licenses/by/3.0/`.

### Registry (`data/registry/sources.csv`, `docs/data/REGISTRY_FORMAT.md`)
- **Columns** (the first eight are the spec's list):
  - `clip_id`, `source`, `source_ref`, `licence`, `speaker_id`, `consent_ref`, `transcript`, `split`;
  - then `dataset`, `tags`, `sha256`, `sample_rate_hz`, `channels`, `n_samples` and `attribution`.
  - The extra columns let the builder find and check each source file, filter by tag, compute durations exactly and write per-file attributions.
- **Values**:
  - LibriSpeech: `clip_id` `ls-<split>-<utterance>` (for example `ls-test-clean-1089-134686-0000`); `source` `librispeech`; `source_ref` the path inside the archive; `speaker_id` the reader ID; `split` `test-clean` or `test-other`; `transcript` verbatim from `*.trans.txt`.
  - MUSAN: `musan-noise-free-sound-0232`, `musan-music-rfm-0058`; `source` `musan`; `split` `noise` or `music`; `speaker_id` and `transcript` empty (non-speech). Tags: `background` for the 37 files that free-sound's ANNOTATIONS lists as background noises; `genre-<g>` and `vocals-no` from rfm's ANNOTATIONS.
  - Owner: `owner-<file stem>`; `source` `owner`; `speaker_id` `owner`; `split` `owner`; `consent_ref` `data/owner_smoke/CONSENT.md`; transcript from `transcripts.csv`.
- **Format**: UTF-8, header row, `\n` line ends, minimal quoting, rows sorted by `clip_id`. An empty field means null. `registry build` regenerates the same bytes from the same inputs.
- **Scope**: the registry catalogues complete subsets (every test-clean and test-other utterance, all free-sound noise and all rfm music), not only the 60 smoke clips. The pack spec then selects from it, and later packs reuse it. About 7,200 rows, about 1.5 MB.

### Commands (addition D3)
- `python -m aqis_lab registry fetch <dataset> [--cache DIR]`: download, check, extract (FR-0.4-02). The default cache is `data/raw/aqis_lab`.
- `python -m aqis_lab registry build [--cache DIR] [--out data/registry/sources.csv]`: regenerate the registry from the fetched datasets and `data/owner_smoke/`. It refuses to write an invalid registry.
- `python -m aqis_lab registry validate [FILE]`: FR-0.4-01 checks. It prints `OK` and the row counts per source, or one line per problem (`row <n> column <name>: <reason>`).
- `python -m aqis_lab pack build SPEC --out DIR [--registry FILE] [--datasets FILE] [--cache DIR]` and `python -m aqis_lab pack verify DIR`.
- All paths are repository-relative defaults resolved from the repository root, or command-line arguments. Exit codes: 0 success; 1 validation or verification failed; 2 usage, input, download or I/O error.

### Pack spec (`packs/specs/smoke_v1.yaml`)
- Top level: `spec_version: 1`, `manifest_id: smoke`, `version: 1.0.0`, `purpose`, `created_utc` (question 5), `seed: 20260927` (fixed now, before any build, and never tuned to results), `limits` (at most the hard caps), `categories`.
- YAML is loaded with a loader that rejects duplicate keys. The spec is validated against `pack_spec.v1.json`, so an unknown key or a wrong type is an error.
- **Categories, in archive order** (question 7):
  - `test-clean`: 20 clips from `librispeech`/`test-clean`, 3 to 15 s, distinct speakers.
  - `test-other`: 10 clips from `librispeech`/`test-other`, 3 to 15 s, distinct speakers.
  - `noisy`: 10 mixes.
    - Speech: 10 other test-clean utterances (3 to 15 s, distinct speakers, not used elsewhere in the pack).
    - Noise: free-sound files tagged `background`, long enough for the speech clip, each used once.
    - SNR, in selection order: 5, 5, 5, 5, 10, 10, 10, 20, 20, 20 dB.
  - `non-speech`: 4 noise excerpts (free-sound files not tagged `background`), 4 music excerpts (rfm), each 10.0 s at a seeded offset; 2 silences of 5.0 s and 10.0 s.
  - `owner`: all 10 `owner` rows, 3 to 8 s each.
- **Licence filter**: only licences without ShareAlike or NonCommercial terms may enter the pack (question 2).

### Selection (deterministic)
- For each category in order, candidates are the registry rows that match its filters and are not yet used in the pack.
- Candidates are ordered by `sha256("aqis-pack-select-v1|<seed>|<category>|<clip_id>")` and taken in that order, skipping a speaker already taken in that category, until the count is reached. Fewer candidates than the count is an error naming the category.
- Offsets (noise in a mix, excerpts) are `int(sha256("aqis-pack-offset-v1|<seed>|<clip_id>"), 16) mod (source samples − clip samples + 1)`.
- Nothing depends on registry row order, `PYTHONHASHSEED`, the clock or the Python version's `random` module.

### Clips, recipes and mixing (`mix.py`, recipe v1)
- **Clip IDs.** Clips taken as they are keep their registry `clip_id` (for example `ls-test-clean-…`, `owner-…`). Derived clips get `<manifest_id>-<kind>-<nn>`: `smoke-mix-01`, `smoke-noise-01`, `smoke-music-01`, `smoke-silence-01`. The builder rejects a derived ID that is also a registry ID.
- **Clips taken as they are** (LibriSpeech, owner): `recipe` is `null`.
  - The samples are unchanged and written into a canonical WAV: RIFF, a 16-byte PCM `fmt ` chunk and a `data` chunk, 44-byte header. Any other chunks in the source, such as recorder metadata in owner files, are dropped.
  - FLAC decoding is checked against the file's STREAMINFO MD5 (finding 6).
- **Recipe v1** (JSON Schema `aqis_lab/packs/schemas/recipe.v1.json`, documented in `SMOKE_PACK.md`; question 6):
  - common: `recipe_version` `"1.0"`, `kind`, `source_clip_ids`, `length_samples`;
  - `mix`: `speech_clip_id`, `noise_clip_id`, `snr_db`, `seed`, `noise_offset_samples`, `snr_definition`, `speech_gain`, `noise_gain`, `speech_gain_q24`, `noise_gain_q24`, `peak_limited`, `achieved_snr_db`;
  - `excerpt`: `seed`, `offset_samples`;
  - `silence`: `source_clip_ids` is empty and no seed is needed (all samples are 0).
- **SNR definition.** `P_x` = mean of squared 16-bit sample values over the clip length: the whole speech clip, and the noise segment of the same length starting at the offset. The target noise gain is `g = sqrt(P_s / (P_n · 10^(SNR/10)))`, with speech gain 1.
- **Arithmetic.**
  - Sums of squares are exact integers. `g` is computed with Python's `decimal` at 50 digits, using `ln`, `exp` and `sqrt`, which the module rounds correctly. It is then quantised to `round(g · 2^24)`.
  - Mixed sample = `(s · 2^24 · a + n · b + 2^23) >> 24` in 64-bit integers, where `a` and `b` are the quantised gains.
  - If any sample would leave the 16-bit range, both gains are scaled by the same factor, computed the same way; this keeps the SNR and sets `peak_limited: true`.
  - `achieved_snr_db` is computed from the quantised gains, rounded to 4 decimals.
  - No step uses platform maths libraries, so the same inputs and seed give the same bytes on every machine.
- **Non-speech excerpts** have `transcript` and `speaker_id` null. **Mixes** keep the speech clip's transcript and speaker.
- **Licences of derived clips.** A mix gets `CC-BY-4.0 AND LicenseRef-public-domain`, an rfm excerpt `CC-BY-3.0`, a free-sound excerpt `LicenseRef-public-domain`, a silence `CC0-1.0`.

### Archives, layout and manifest (`archive.py`, `build.py`)
- **Layout of `data/packs/smoke/v1/`**: `manifest.json`, `LICENCES.md`, `build_record.json` (D5) and one or more tar shards per category, named `<manifest_id>-<version>-<category>-<nnn>.tar` (for example `smoke-1.0.0-noisy-000.tar`).
  - One shard per category keeps each category, and the owner recordings in particular, in their own archive. It also lets a runner fetch one category.
  - The smoke pack will have 5 shards, about 14 MB in total.
- **Tar format**: uncompressed (WAV hardly compresses, and plain tar can be streamed and read by offset), Python `tarfile` PAX format.
  - Every member is a regular file with mode `0644`, uid and gid 0, empty user and group names, and mtime = `created_utc` as whole seconds. There are no directory entries.
  - Members are ordered by category (spec order), then `clip_id`. Member path: `<category>/<clip_id>.wav`, or `<category>/<nnn>/<clip_id>.wav` when a category has more than 1,000 clips.
- **Limits** (FR-0.4-06): 200 MB means 200,000,000 bytes, the stricter reading. "Files per folder" counts every entry (files and subfolders). Both limits are checked when building and when verifying, and documented in `SMOKE_PACK.md` "Layout".
- **Manifest**:
  - written as UTF-8 JSON with sorted keys, 2-space indent and a final newline, the same bytes on every build;
  - every field as in the WP-0.2 contract: `schema_version` `"1.0"`, `created_utc` from the spec, `duration_s` = `n_samples / sample_rate_hz`, `sha256` of each WAV file, `archive` and `member_path`, `tags` (for example `["clean","speech"]`, `["noisy","snr-5","speech"]`, `["music","non-speech"]`);
  - `validate_manifest` is run before the manifest is written.
- **`build_record.json`** (addition D5): canonical JSON with the SHA-256 and file names of the pack spec, the registry and `datasets.yaml`, the seed, the builder version and the manifest's canonical SHA-256. It is how "every random step takes an explicit seed, recorded in its outputs" holds for the selection step, whose result (clips taken as they are) has `recipe: null`. It holds no git commit or time, so rebuilding on a later commit with the same inputs gives the same file.
- **Atomic build**: output is staged in a sibling `.<name>.partial` folder and renamed at the end. If the build fails, the staging folder is removed. If `--out` or the staging folder already exists, the build exits 2 and changes nothing.

### Verify (`verify.py`)
`pack verify DIR` checks, reporting every problem found:
1. `manifest.json` parses strictly and passes `validate_manifest`. Each clip's `recipe` passes recipe v1 when it is not null.
2. The folder holds exactly `manifest.json`, `LICENCES.md`, `build_record.json` (if D5) and the listed archives: a missing or an extra file is a problem. The folder has at most 1,000 entries.
3. For each archive: its size and SHA-256 equal the manifest; it is at most 200,000,000 bytes; it opens as a tar.
   - Every member must be a regular file with a safe path: links, devices and directories are problems.
   - The members equal the manifest's clips for that archive exactly (missing, extra or duplicate members are problems), and `n_members` matches.
   - No folder inside the archive has more than 1,000 entries.
4. For each member: its SHA-256 equals the clip's `sha256`. Its WAV header is canonical 16-bit PCM, and its sample rate, channels and duration equal the manifest's `sample_rate_hz`, `channels` and `duration_s`.
5. `LICENCES.md` names every clip with its licence.
6. The report ends with counts per category (split), for example `pack smoke 1.0.0: OK, 60 clips in 5 archives; test-clean 20, test-other 10, noisy 10, non-speech 10, owner 10`.

Verify needs no source files and no network, so it runs the same on the cloud VM, Colab and Oracle.

### Parts that do not need the owner recordings
Everything except these can be built and tested before `data/owner_smoke/` arrives: the registry's owner rows, the committed smoke pack, AT-0.4-01, AT-0.4-02, and the real NFR-0.4-01 measurement. That covers all code and tests (with generated test inputs), the fetch of the public sources and the public part of the registry. If the recordings are still missing when I reach the pack build, I stop and ask; I never build the pack without them.

### Must-catch proof (planned)
| # | Behaviour | Break I will make in a copy under `/tmp` | Tests that must fail |
| --- | --- | --- | --- |
| 1 | A clip without a licence is rejected; an owner recording without a consent reference is rejected | skip the licence check; accept an empty `consent_ref` for `owner`; accept a `consent_ref` that points to no file | `test_FR_0_4_01_rejects_missing_licence`, `test_FR_0_4_01_rejects_owner_row_without_consent`, `test_FR_0_4_01_rejects_consent_ref_that_does_not_resolve` |
| 2 | Building twice gives byte-identical archives and manifest | use the file's real mtime in tar headers; order members by registry row order; write `created_utc` from the clock | `test_FR_0_4_05_build_twice_byte_identical`, `test_FR_0_4_05_tar_headers_are_normalised`, `test_FR_0_4_03_selection_ignores_registry_row_order`, `test_FR_0_4_05_created_utc_comes_from_spec` |
| 3 | `pack verify` fails on any changed, missing or extra member | skip the member hash check; skip the "extra member" check; skip the "missing member" check | `test_FR_0_4_05_verify_fails_on_changed_member`, `test_FR_0_4_05_verify_fails_on_extra_member`, `test_FR_0_4_05_verify_fails_on_missing_member` |
| 4 | The smoke pack has exactly the category counts the spec lists | change a count in a copy of the spec; make the builder take one clip fewer when a category's candidates run short instead of failing | `test_FR_0_4_03_smoke_spec_declares_exact_composition`, `test_FR_0_4_03_fails_when_too_few_candidates`, `test_FR_0_4_03_builder_selects_exact_counts` |
| 5 | Mixing records its recipe, and the same seed reproduces the same audio | drop `noise_gain` from the recipe; derive the offset from `random.random()` without the seed | `test_FR_0_4_04_recipe_records_sources_snr_seed_gains`, `test_FR_0_4_04_clip_rebuilt_from_recipe_alone`, `test_FR_0_4_04_same_inputs_and_seed_byte_identical` |
| 6 | The folder and archive size limits are enforced | raise the archive cap to 300 MB; remove the per-folder split; remove verify's size check | `test_FR_0_4_06_rejects_limits_above_hard_caps`, `test_FR_0_4_06_splits_member_folders_at_1000_files`, `test_FR_0_4_06_verify_fails_on_oversized_archive` |

## Owner needs
| # | What | Why | Needed by |
| --- | --- | --- | --- |
| 1 | Answers to questions 1 to 9 below, as CONDITIONS in `docs/approvals/WP-0.4.md` (or "as recommended") | They decide the sources and downloads (the spec's stop-and-ask for FR-0.4-02), the licence policy, how personal data is handled and the pack format that later WPs depend on | Before `/wp-build WP-0.4` |
| 2 | `data/owner_smoke/` committed to `main`: 10 WAV recordings of 3 to 8 s, 16 kHz mono 16-bit PCM, named with lowercase letters, digits and hyphens (for example `01.wav` … `10.wav`); `transcripts.csv` with the header `file,text` and one row per WAV; `CONSENT.md` stating that the speaker agreed to lab use. Upload on GitHub: in `main`, **Add file → Upload files**, into a folder `data/owner_smoke/`. Please use neutral sentences with no personal details (no names, addresses or numbers that identify you) | FR-0.4-03 requires 10 owner recordings; FR-0.4-01 requires their consent reference | Before the pack build step (see "Parts that do not need the owner recordings"). Everything else can go ahead without them |

No network allowlist change is needed: `www.openslr.org` and PyPI are reachable from this VM. The download is about 11.8 GB (question 1). No credentials, Colab runs or Oracle runs are needed.

## Owner-run checks planned
None. The spec runs this WP on the cloud VM only, and everything in it can run here. CI (GitHub Actions, Ubuntu) runs the fast suite on a second machine, including the build-twice determinism tests on generated inputs and `pack verify` on the committed smoke pack. The committed pack is what Colab and Oracle use (WP-0.5 copies it from the repository). Identical Vosk results across machines are proved later by WP-0.7 (exit criterion E1).

## Risks and questions
### Questions for you
1. **(FR-0.4-02, stop-and-ask) Where the sources come from.** `corpus-v1.tar.gz` holds processed VAD clips without transcripts, without test-other and without MUSAN noise or music files (finding 2), so it cannot be used. Download options:
   - **(a) Recommended.** OpenSLR's main host `www.openslr.org`, reachable now at 15 to 17 MB/s, no allowlist change:
     - `https://www.openslr.org/resources/12/test-clean.tar.gz`: 346,663,984 bytes, CC BY 4.0;
     - `https://www.openslr.org/resources/12/test-other.tar.gz`: 328,757,843 bytes, CC BY 4.0;
     - `https://www.openslr.org/resources/17/musan.tar.gz`: 11,086,114,085 bytes, CC BY 4.0 as a corpus, with per-file licences inside (question 2).
     - About 12 minutes for MUSAN on this VM, and about 14 GB of disk for the kept archives and extracted subsets. Each archive is checked against OpenSLR's published MD5 and a SHA-256 pin before use. Only the registry, the smoke pack and `LICENCES.md` are committed, never raw corpora.
   - **(b)** An OpenSLR mirror (`openslr.elda.org`, `openslr.trmal.net`, `openslr.magicdatatech.com`). These are blocked here (403), so you would have to add them to the cloud environment allowlist, and they offer nothing over (a).
   - **(c)** Third-party copies (for example Hugging Face repackagings). Not recommended: they are repackaged by others, so the origin and licence trail is weaker.
2. **MUSAN subsets and the licence policy** (finding 5).
   - **(a) Recommended.** Catalogue only `noise/free-sound` (Public Domain for every file) and `music/rfm` (Kevin MacLeod, CC BY 3.0 for every track, all instrumental), and let only licences without ShareAlike or NonCommercial terms into packs.
     - The licence of every registry row then comes from one pinned LICENSE file per subset. The attribution text for every rfm track is generated from its title.
     - Mixes and excerpts carry no ShareAlike obligation.
     - The other MUSAN subsets (sound-bible, the four other music folders, speech) are left out. They can be added later with per-file licence parsing.
   - **(b)** Catalogue all MUSAN subsets and parse every per-file licence from the free-text LICENSE files. That needs a hand-checked mapping from about 20 differently worded licence statements. Derived clips from ShareAlike tracks would then have to carry that ShareAlike licence.
3. **Owner recordings: format and licence labels.**
   - **Format.** **(a) Recommended:** the builder requires 16 kHz mono 16-bit PCM WAV and rejects anything else, naming the file, its actual format and a one-line conversion command (`ffmpeg -i in.m4a -ac 1 -ar 16000 -sample_fmt s16 out.wav`). **(b)** The builder converts other formats itself. This needs resampling code whose output depends on the method chosen and is harder to reproduce exactly.
   - **Licence labels.**
     - Owner recordings: **recommended** `LicenseRef-AQIS-owner-consent`, "Recorded by the lab owner for AQIS lab use only; not for redistribution; consent: `data/owner_smoke/CONSENT.md`". Tell me if you want other wording.
     - Silence generated by the lab (no third-party material): **recommended** `CC0-1.0`.
4. **Real personal data in the repository.** The overview says never to commit real personal data, and the audit protocol (A14) checks for it. But the spec puts your recordings in `data/owner_smoke/` and inside the built pack (`data/packs/smoke/v1/`), and WP-0.5 copies packs from the repository to Colab.
   - **(a) Recommended.** Commit `data/owner_smoke/` and the whole pack, owner shard included, to this private repository. Your consent note covers lab use, and the recordings contain only neutral sentences. The approval records this decision so the audit treats it as approved. The owner shard is a separate archive (`smoke-1.0.0-owner-000.tar`), so it can be removed or replaced on its own.
   - **(b)** Keep the owner recordings and the owner shard out of git. This needs a `.gitignore` change (GUARDED, `ALLOW-EDIT`) and another way to move them to the cloud VM, Colab and Oracle, which the phase 0 specs do not provide. A fresh cloud session could then not run AT-0.4-02, and CI could not verify the committed pack.
5. **(Deviation D1) `created_utc` and byte-identical builds.** The manifest contract requires `created_utc` ("when the manifest was written"), but AT-0.4-01 requires two builds to give identical manifests.
   - **(a) Recommended.** The pack spec states `created_utc` (the date the pack version is released) and the builder writes it unchanged. The tar mtimes use the same value. A new pack version gets a new value.
   - **(b)** The build time. This contradicts AT-0.4-01 and changes the run card's `pack.sha256` on every rebuild.
   - **(c)** The build time, left out when comparing builds. This weakens AT-0.4-01 and must-catch 2.
6. **(Deviation D2) Where the recipe members are defined** (finding 8).
   - **(a) Recommended.** Keep the manifest contract at 1.0, where `recipe` is an open object. Recipe v1 is defined by `aqis_lab/packs/schemas/recipe.v1.json`, carries its own `recipe_version`, is documented in `SMOKE_PACK.md` and is checked by `pack build` and `pack verify`. I update the `/clips/*/recipe` meaning cell in `PACK_MANIFEST.md` to point there. No WP-0.2 test changes.
   - **(b)** Manifest contract 1.1 with the recipe members in the schema, as the WP-0.2 plan anticipated. This needs `ALLOW-EDIT` for three existing WP-0.2 tests:
     - `test_FR_0_2_06_rejects_newer_minor_version` uses `1.1` as "newer";
     - `test_FR_0_2_06_rejects_unknown_major_version` expects the text "up to 1.0";
     - `test_FR_0_2_03_recipe_accepts_any_members` expects any members to pass.
     
     It also changes the WP-0.2 validator, schema, document and fixture. It is larger and touches merged, audited code.
7. **Smoke pack composition details** (FR-0.4-03 fixes the counts, not these):
   - (a) SNRs for the 10 mixes: 4 at 5 dB, 3 at 10 dB, 3 at 20 dB.
   - (b) Mixes use 10 test-clean utterances that are not among the 20 clean clips. Every speech clip in the pack then has its own transcript, so a runner that mixes up clips shows up as a WER jump.
   - (c) Non-speech: 4 noise excerpts, 4 instrumental music excerpts (10 s each) and 2 digital silences (5 s and 10 s, all samples 0).
   - (d) LibriSpeech clips of 3 to 15 s with distinct speakers per category. Mix noise from the 37 free-sound "background" (ambient) recordings; non-speech noise from the other free-sound files.
   
   **Recommended: accept (a) to (d).** Estimated pack size: about 430 s of audio, about 14 MB.
8. **Lock additions.** Add `soundfile` (FLAC decoding; BSD-3-Clause) and `numpy` to `phase0.in`, pinned by the lock. The resulting lock adds 5 packages (finding 7); `numpy` is about 16 MB per wheel. **Recommended: accept.**
9. **(Additions D3 to D5) Beyond the spec's deliverables.**
   - **D3:** the `registry fetch|build|validate` commands, so acquisition and registry generation are repeatable commands on every platform rather than manual steps.
   - **D4:** `data/registry/datasets.yaml`, holding download URLs and pins, extract patterns, the licence table and the attribution texts, all of which `sources.csv` and `LICENCES.md` are generated from.
   - **D5:** `build_record.json` in the pack folder, recording the pack spec, registry and dataset file hashes and the seed. This is how the selection seed is "recorded in its outputs".
   
   **Recommended: accept all three.** Without D3, the registry would be generated by a script outside the CLI. Without D4, the same facts would sit in code constants. Without D5, the selection seed is recorded only in the committed pack spec.

### Design decisions made in this plan (approving the plan accepts them)
- The registry catalogues complete subsets rather than only the smoke clips; the pack spec selects from it.
- Clips taken as they are keep their registry `clip_id`; derived clips get pack-scoped IDs checked against the registry.
- One tar shard (or more, at the size limit) per category, uncompressed, with normalised headers.
- 200 MB means 200,000,000 bytes; "files per folder" counts every entry.
- SNR over the whole speech clip (mean square), not an active-speech level. It is simple, exact and documented; an active-speech level (ITU-T P.56) can be added later as a new recipe version.
- Owner WAV files are rewritten with a canonical header. Metadata chunks are dropped, so recorder details do not travel into the pack.
- `pack build` never overwrites an existing folder; `pack verify` needs no sources or network.

### Other risks
1. **MUSAN download size.** 11.1 GB must be downloaded once per machine that rebuilds the pack, about 12 minutes here. Colab and Oracle normally use the committed pack and need not fetch. An interrupted download resumes with range requests. If OpenSLR is down or fails twice in the build, I stop and ask.
2. **MUSAN pin.** The SHA-256 above comes from one planning stream that was not compared with the published MD5. The build checks the MD5 first and stops if it differs.
3. **Audit and re-run time.** AT-0.4-01 and the `slow`/`network` tests need the fetched sources (about 13 minutes, 14 GB). The fast suite and CI use only generated inputs and the committed pack.
4. **Repository size.** The committed pack (about 14 MB) and registry (about 1.5 MB) add to the history on every rebuild that changes them. A new pack version is a new folder, and old versions stay unchanged.
5. **FLAC decoder.** Decoding relies on the libsndfile bundled with `soundfile`. The STREAMINFO MD5 check makes any decoder difference an error rather than a silent change.
6. **Oracle (aarch64 possible).** `soundfile` and `numpy` have manylinux_2_28 aarch64 wheels, so they need glibc 2.28 or newer, as `pyarrow` already does. WP-0.6 confirms this on the real VM.
7. **Free-sound content.** The noise README says the ambient recordings "usually do not feature any intelligible speech". No one listens to the clips in this WP, so "non-speech" rests on MUSAN's own labels, and `SMOKE_PACK.md` says so.

## Deviations
- **D1**: `created_utc` comes from the pack spec, so two builds give identical manifests (question 5).
- **D2**: recipe v1 is defined by a lab schema inside the manifest's open `recipe` object, and the manifest contract stays at 1.0 (question 6).
- **D3**: `registry fetch|build|validate` commands (question 9).
- **D4**: `data/registry/datasets.yaml` (question 9).
- **D5**: `build_record.json` in the pack folder (question 9).
- **D6** (owner decision, approval conditions): the 10 owner recordings of FR-0.4-03 are replaced by 10 synthetic TTS clips from `data/tts_smoke/`: category `tts`, source `tts`, Apache-2.0 with attribution to hexgrad/Kokoro-82M, no consent reference. See "Amendment after approval".

Everything else fills in something the spec leaves open and is listed under "Design details" and "Design decisions"; none of it contradicts the spec.

## Measurements
All planning measurements were made in the scratchpad, never in the repository.
- **Downloads.** Range downloads of 50 MB: 16.8 MB/s (MUSAN) and 14.5 MB/s (test-clean). Full LibriSpeech downloads: test-clean MD5 `32fa31d27d2e1cad72775fee3f4849a9` and test-other MD5 `fb5a50374b501bb3bac4815ee91d3135`, both equal to OpenSLR's `md5sum.txt`; SHA-256 as in finding 3.
- **MUSAN metadata.** One full stream of `musan.tar.gz` gave SHA-256 `86d1061c7e15b5c9e906777685c519701df51bfde3001e1070dcc9ffac955ee1` (not yet compared with the published MD5 `0c472d4fc0c5141eca47ad1ffeb2a7df`) and the README, LICENSE and ANNOTATIONS files described in finding 5. Counts: rfm 147 tracks (all vocals `N`, all Kevin MacLeod); sound-bible 86 files; free-sound ANNOTATIONS lists 37 background noises.
- **FLAC exactness.** `soundfile 0.14.0` with libsndfile 1.2.2 decoded 300 test-clean utterances in 0.9 s. For all 300, the MD5 of the decoded 16-bit samples equals the STREAMINFO MD5.
- **Disk estimate.** Kept archives: 11.1 GB (MUSAN) + 0.68 GB (LibriSpeech). Extracted: LibriSpeech test FLAC 0.72 GB, free-sound about 0.7 GB (6 h of noise at 16 kHz), rfm about 0.9 GB (147 tracks). About 14 GB in total, of 30 GB free.
- **Lock trial.** As in finding 7.
