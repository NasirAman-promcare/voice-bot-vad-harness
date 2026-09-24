# WP-0.1 — Tier 2 VAD transport baseline (owner-run)

- **Depends on**: none
- **Runs on**: the Oracle VM with the self-hosted Jitsi, run by the owner
- **Read first**: the harness README and its Tier 2 run instructions

## Goal
Finish the full Tier 2 VAD run on the real network with the existing harness, unchanged, and store the results as the transport baseline for every later live test.

## Owner steps
1. Run the full Tier 2 run on the real network with the harness exactly as it is.
2. Commit the raw outputs (reports, configs, logs; no audio with personal data) to `docs/baselines/tier2_vad/<YYYY-MM-DD>/raw/`.
3. In a Claude session, run `/wp-start WP-0.1`, approve, then `/wp-build WP-0.1`.

## Functional requirements (Claude)
- **FR-0.1-01** Check the raw folder is complete: run configuration, network description, per-VAD metrics and logs. List anything missing and stop and ask; never reconstruct missing data.
- **FR-0.1-02** Write `docs/baselines/tier2_vad/<date>/SUMMARY.md`: setup, VADs, conditions, and headline metrics per VAD. Every number cites its source file and field or line. Nothing is estimated; a derived number shows its formula and inputs.
- **FR-0.1-03** No code and no harness file changes in this WP.

## Acceptance
- **AT-0.1-01** The auditor checks five random numbers in `SUMMARY.md` against the raw files.
