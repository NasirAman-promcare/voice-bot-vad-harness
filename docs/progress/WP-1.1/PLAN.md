# PLAN: WP-1.1 S1 ASR benchmark

Spec: `docs/specs/sprints/WP-1.1-S1-asr-benchmark.md` (section 6)  ·  Branch: `s1/asr-bench`  ·  Base: `origin/main` at `33616e0`

## What gets built
- `aqis_lab/bench/`: `config`, `sources`, `select`, `conditions`, `models`, `run`, `score`, `report`, plus `prep` (the spec's "prep" action needs its own module) and `__main__` (`prep`, `smoke`, `run`, `speed`, `score`, `report`).
- `config/aqis_lab/s1.yaml`: Appendix A, plus cleaning rules per source, entity categories, the telephone selection flags and each model's licence.
- Hash-pinned locks `s1-prep`, `s1-hf`, `s1-nemo`, `s1-qwen` (uv 0.8.17, Python 3.13, x86_64, `-c phase0.txt`, command in each header).
- `notebooks/aqis_lab/s1_asr_benchmark.ipynb` (STAGE and MODELS in cell 1, unit log, `runtime.unassign()` last).
- One CI step in the `lab` job: `sudo apt-get install -y --no-install-recommends libopus0`.

## Order
1. Ruler tests first (`tests/aqis_lab/test_s1_*.py`, brief 6.4 items 1 to 10, plus the strict config, resumable prediction files and the light-runner import check). They failed on import before any bench code existed.
2. Code, config, locks, notebook, CI step.
3. Fast suite and gate green, PR `WP-1.1: S1 ASR benchmark`, merge, tag `s1-colab-1`.

## Facts found while planning (17 Oct 2026; dataset cards, parquet footers, and the text columns only, no audio)
- **EdAcc** (19,137 rows) has no duration column, so prep preselects 3 x N and measures. Tags counted: `<LAUGH>` 1,668, `<DTMF>` 639, `<OVERLAP>` 454, `<NO-SPEECH>` 160, `<FOREIGN>` 68, `<BREATH>` 27, `<COUGH>` 22, `<RING>` 15, `<LIPSMACK>` 8, `<CLICK>` 5, plus the token `IGNORE_TIME_SEGMENT_IN_SCORING` (123). Rules: strip the non-words, drop overlap, foreign, no-speech and the ignore token. L1 counts in test + validation: Mainstream US English 752, Hindi 350, Urdu 274, Sinhalese 95, Indian English 654.
- **Svarah**: 6,656 rows, no speaker or speech-type column. The speaker is a hash of its 8 attribute columns (115 distinct, the paper says 117), and the slice is picked without the 100/150/150 split (the prep report says so).
- **Eka** (3,619 rows): entities are a JSON string `[[text, category, [[start, end]]], ...]`. Categories: `drugs` 2,504, `clinical_findings` 5,615, `diagnostics` 1,021 (the brief's "test"), `advices` 376 and `misc_medical` 1,145 (both left out). Only 110 rows are `conversation`; 2,206 are isolated entities and 1,303 narrated sentences, so the slice mixes them (recording context is kept in the metadata). Speaker is null in 110 rows (session ID is used).
- **Earnings-22 `chunked`** (57,391 segments, 125 calls): the call is the bootstrap cluster. Tags: `<inaudible>` 662, `<unk>` 135, `<laugh>` 126, `<crosstalk>` 113, `<affirmative>` 50, `<silence>` 36, a few others. 6,625 segments of 3 to 20 s have at least 2 digit tokens. The card says CC BY 4.0, the brief says CC BY-SA 4.0; prep records both.
- **HarperValleyBank** keeps per-role 8 kHz channel files and transcript segments with `offset_ms` and `duration_ms` (README only; the audio was not fetched here).
- Parquet row groups hold about 100 rows (18 to 35 MB), so a pick of N scattered utterances downloads roughly the row groups it touches.

## Choices that differ from the brief's wording
- `datasets` is not in `s1-prep`: prep reads the parquet files through `huggingface_hub.HfFileSystem` and pyarrow, so only the rows chosen are downloaded.
- Unknown reference tags or entity categories stop prep with a list instead of being guessed (the brief says to inspect real tags first).
- Libraries outside the phase 0 lock load through `aqis_lab.bench.lib()` (importlib), as the Parakeet adapter does for torch and NeMo. Two Phase 0 guard tests (`test_NFR_0_0_03_imports_are_stdlib_or_pinned`, `test_FR_0_7_03_torch_and_nemo_imported_only_in_gpu_adapter`) scan for literal imports and name no other file; they are unchanged and pass. The owner may prefer to extend them instead.
