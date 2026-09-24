# WP-0.4 — Source registry, pack builder and smoke pack

- **Depends on**: WP-0.0, WP-0.2
- **Runs on**: cloud VM
- **Read first**: AQIS Test Lab Build Plan sections "Dataset architecture" and "Phase 0"; the pack manifest contract

## Goal
A registry that records where every clip came from and under what licence, a deterministic pack builder, and the 60-clip smoke pack.

## Deliverables
- `data/registry/sources.csv` and `docs/data/REGISTRY_FORMAT.md`
- `aqis_lab/registry/`, `aqis_lab/packs/` with `python -m aqis_lab pack build|verify`
- `packs/specs/smoke_v1.yaml`
- Built smoke pack in `data/packs/smoke/v1/` (manifest, archive shards, `LICENCES.md`)
- `docs/data/SMOKE_PACK.md`

## Functional requirements
- **FR-0.4-01** The registry records, for every source clip: `clip_id`, source, source reference, licence, speaker ID, consent reference (required for owner recordings), transcript (for speech), split. Validation rejects a missing licence or a missing required consent.
- **FR-0.4-02** Source acquisition: first inspect `corpus-v1.tar.gz` read-only and report its contents in `docs/data/SMOKE_PACK.md`. Use it if it holds the needed LibriSpeech test-clean and test-other utterances with transcripts and MUSAN noise and music; otherwise stop and ask with download options (hosts, sizes, licences). Never commit large raw corpora.
- **FR-0.4-03** Smoke pack composition, exactly: 20 LibriSpeech test-clean, 10 LibriSpeech test-other, 10 noisy mixes (clean speech with MUSAN noise at 5, 10 and 20 dB SNR, seeded), 10 non-speech clips (noise, music, silence), and 10 owner recordings from `data/owner_smoke/`. All 16 kHz mono 16-bit PCM WAV.
- **FR-0.4-04** Mixing is deterministic: the same inputs and seed give byte-identical output. Each mixed clip records its recipe: source clip IDs, SNR, seed, gains.
- **FR-0.4-05** `pack build` writes a manifest valid under the WP-0.2 schema and tar shards with SHA-256, in deterministic order. `pack verify` recomputes every hash and checks every manifest entry.
- **FR-0.4-06** Drive-friendly layout: at most 1,000 files per folder and at most 200 MB per archive, documented.
- **FR-0.4-07** `LICENCES.md` lists every source with its licence and the attribution text CC BY 4.0 requires.

## Non-functional requirements
- **NFR-0.4-01** Building the smoke pack takes under 2 minutes on the cloud VM.

## Acceptance commands
- **AT-0.4-01** Building twice gives identical manifest and archive hashes.
- **AT-0.4-02** `python -m aqis_lab pack verify data/packs/smoke/v1` passes; counts per category match FR-0.4-03.
- **AT-0.4-03** The audit gate passes with `--wp WP-0.4`.

## Owner needs
- `data/owner_smoke/`: 10 WAV recordings of 3 to 8 seconds, `transcripts.csv` (file, text), and `CONSENT.md` stating the speaker agreed to lab use.
- Network hosts, if Claude reports a download is blocked.

## Stop and ask if
- Owner recordings are missing, the corpus lacks transcripts, or a download host is blocked.
