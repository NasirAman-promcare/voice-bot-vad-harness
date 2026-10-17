# AQIS Lab: instructions for Claude Code

**Results first (since 17 Oct 2026).** We measure which speech models work for our callers, where each one breaks, and whether a mix of models beats the best single one. Every sprint ends in numbers, not tooling.

- **Callers:** US healthcare providers, patients and insurance reps. US English and South Asian accents. 8 kHz phone lines and WebRTC (Opus).
- **Current sprint:** the newest brief in `docs/specs/sprints/` (the session hook prints it). Results go in `docs/results/S<n>/`.

## Seven rules
1. **Numbers every sprint.** "Done" means a scorecard and a one-page decision note.
2. **Reuse first.** Use libraries, and Phase 0 code such as `aqis_lab/scoring`, `packs/mix.py`, `unitlog.py` and `registry fetch`. Write glue, not frameworks. Ask before adding a framework or a service.
3. **One config and one notebook per experiment.** Every result row records the model, model revision, slice, condition, seed, git commit and GPU.
4. **Test the ruler, not the plumbing.**
   - The normaliser, WER, entity scoring, bootstrap, oracle and audio conditions get tests with independently worked-out expected values.
   - The Colab smoke run checks the model wrappers.
5. **One review per sprint.**
   - Branch name: `s<n>/<topic>`.
   - PR title: `WP-1.<n>: <what>`. CI reads the ID.
   - CI also needs `docs/progress/WP-1.<n>/PLAN.md` and `EVIDENCE.md`, a few lines each. EVIDENCE holds the test command and its real output.
   - Merge the PR yourself once CI is green.
6. **Small first.** Run a smoke test (3 clips), then a pilot (100 per slice), then the full set.
7. **Write the code yourself.** No work orders, relays or outside AIs.

## Honesty (the stop gate enforces part of this)
- Never invent numbers, transcripts or results. If an input is missing, the run stops with a clear error; never use a stand-in.
- No stubs, swallowed errors, or skipped or weakened tests.
  - The gate flags TODO, "placeholder", "dummy", "fake", "temporary", "for now" and `except: pass` in new lab lines.
  - Name things plainly ("warm-up clip").
- Cite the run, the commit and the results file for every number.
- If one approach fails twice, change approach once. Then tell the owner what is blocked.

## Where things run
- **Here (cloud session):** code and fast tests only. Never download corpora or models.
- **Colab:** all GPU work; the owner runs it, with about 70 units until renewal.
  - **GPU:** L4 by default (bf16, about 1.7 units an hour). T4 is only for NeMo models. Use an A100 only with the owner's OK.
  - **Data:** copy from Drive to local disk, compute, then write back. Keep shards resumable and no longer than 30 minutes.
  - **Units:** log them with `python -m aqis_lab unitlog`, and free the runtime at the end.
  - **Never:** servers, tunnels or proxies.
- **Oracle (Arm CPUs, no GPU):** CPU latency and the live Jitsi path, from Sprint 2.

## Security and data
- **Never commit** secrets, tokens or personal data.
- **Data:** use public datasets only, and record each slice's licence. Audio and per-utterance texts stay on Drive; the repo gets aggregates only.
- **Keys** live in Colab Secrets:
  - `GITHUB_TOKEN` goes in through `http.extraHeader`.
  - `HF_TOKEN` goes into one subprocess's environment.
  - Never put a key in URLs, `.git/config`, logs or env files.
- **Not allowed:** paid APIs, pooling free-tier quotas across accounts, and `apt-get` or `sudo` inside tests.

## Paths
- **Code and files:** lab code in `aqis_lab/` (sprint code in `aqis_lab/bench/`). Tests in `tests/aqis_lab/` with unique names. Configs in `config/aqis_lab/`, notebooks in `notebooks/aqis_lab/`.
- **Locks:** in `requirements/aqis_lab/`. Pin with `uv pip compile --generate-hashes`, and put the command in the lock header.
- **New modules:** each new `aqis_lab` module opens with a docstring. Its `CAPABILITIES:` line names what the module does and its tests; the gate checks for it.
- **Owner-only (hooks block edits):** `CLAUDE.md`, `.claude/`, `docs/specs/`, `docs/process/` and `docs/approvals/`. The old VAD harness is guarded (`docs/process/PROTECTED_PATHS.txt`).
- **History (read only if asked):** `docs/archive/`, `docs/progress/` and the rest of `docs/process/`.

## Commands
- Set up: `bash aqis_lab/deploy/dev_bootstrap.sh`
- Fast tests: `.venv/bin/python -m pytest tests/aqis_lab -q --tb=short -m "not slow and not gpu and not colab and not oracle and not network"`
- Gate (the stop hook and CI run it too): `.venv/bin/python -m tools.audit.gate --base origin/main`
