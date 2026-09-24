# Phase 0 — Foundations and plumbing: overview

**Goal:** prove that the same run gives the same result on the cloud VM, Google Colab and the Oracle VM, survives a disconnect, and leaves a traceable record, before any model is judged. Source: AQIS Test Lab Build Plan, phase 0.

## Work packages

| WP | Title | Built by | Depends on | Runs on |
| --- | --- | --- | --- | --- |
| WP-0.0 | Guardrails and audit tooling | Claude | none | Cloud VM, GitHub Actions |
| WP-0.1 | Tier 2 VAD transport baseline | Owner runs; Claude summarises | none | Oracle and Jitsi |
| WP-0.2 | Contracts: event log, run card, pack manifest | Claude | WP-0.0 | Cloud VM |
| WP-0.3 | Text normaliser and scorer | Claude | WP-0.0, WP-0.2 | Cloud VM |
| WP-0.4 | Source registry, pack builder, smoke pack | Claude | WP-0.0, WP-0.2 | Cloud VM |
| WP-0.5 | Platform, doctor, resumable runner, Colab launcher | Claude | WP-0.2, WP-0.4 | Cloud VM, then Colab (owner check) |
| WP-0.6 | Oracle worker, results store, traceability | Claude | WP-0.5 | Cloud VM, then Oracle (owner check) |
| WP-0.7 | First adapters and the smoke run | Claude | WP-0.3, WP-0.5, WP-0.6 | Cloud VM, Colab, Oracle |
| WP-0.8 | Consent, recording guide, filler library v0, targets | Claude drafts; owner decides | none | Documents only |
| WP-0.9 | Phase 0 review | Claude and auditor | all others | Cloud VM |

Order: 0.0 → 0.2 → 0.3 → 0.4 → 0.5 → 0.6 → 0.7 → 0.9, with 0.1 and 0.8 alongside.

## Conventions for every WP

- **Package and command line**: code in `aqis_lab/`; every command runs as `python -m aqis_lab <command> ...`.
- **Tests**: `tests/aqis_lab/`, named `test_<REQ>_<description>`, with markers `slow`, `gpu`, `colab`, `oracle`, `network`.
- **Locks**: `requirements/aqis_lab/phase0.txt` (CPU) and `requirements/aqis_lab/phase0-gpu.txt` (GPU extras), pinned with hashes and generated from `.in` files.
- **Other lab locations**: config in `config/aqis_lab/`, notebooks in `notebooks/aqis_lab/`, data in `data/`, lab documents under `docs/` (not in the protected folders).
- **Identifiers**: `clip_id` uses lowercase letters, digits and hyphens, unique across the registry. IDs derived from content use SHA-256 of canonical JSON.
- **Time**: wall clock as UTC ISO 8601 with `Z`; durations from a monotonic clock in nanoseconds; audio time in seconds.
- **Audio**: phase 0 working format is 16 kHz, mono, 16-bit PCM WAV.
- **Randomness**: every random step takes an explicit seed, recorded in its outputs.
- **Python**: the major.minor version in `docs/environment/colab_probe.txt`.
- **Never commit**: secrets, tokens, real personal data.

## Inputs the owner provides

| Input | Needed by | Where it goes |
| --- | --- | --- |
| Colab probe output | WP-0.0 | `docs/environment/colab_probe.txt` |
| Oracle probe output | WP-0.6 | `docs/environment/oracle_probe.txt` |
| 10 owner recordings with transcripts and a consent note | WP-0.4 | `data/owner_smoke/` |
| Extra network hosts when Claude reports a block | WP-0.4, WP-0.7 | Cloud environment allowlist |
| Google Drive folder `AQIS_LAB` | WP-0.5 | Owner's Drive |
| Read-only GitHub token saved as `GITHUB_TOKEN` in Colab Secrets | WP-0.5 | Colab |
| rclone remote for Google Drive on the Oracle VM | WP-0.6 | Oracle |
| Decisions on targets and retention | WP-0.8 | Approval file |

## Phase 0 exit criteria (checked by `/phase-audit 0`)

- **E1 Parity**: Vosk results on the smoke pack are identical on the cloud VM, Colab and Oracle: same transcript hashes, same WER.
- **E2 Resumability**: a run killed partway resumes without redoing finished shards, on the cloud VM (automated test) and on Colab (owner check).
- **E3 Traceability**: any score row leads back to its run card, pack manifest version, clip, git commit and lock hash.
- **E4 Baseline**: the Tier 2 VAD transport baseline is committed with its summary.
- **E5 Licences**: every smoke clip has a licence entry; owner recordings carry a consent reference.
- **E6 Governance**: every WP is AUDIT-PASS and MERGED; CI is green on `main`; the harness regression baseline is unchanged.
