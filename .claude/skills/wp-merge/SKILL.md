---
name: wp-merge
description: Merge an audited AQIS lab work package through the deterministic merge gate, never by hand. Use when a WP's audit has passed, normally from wp-run.
effort: medium
argument-hint: "[WP-ID]"
---

Merge work package $ARGUMENTS.

## When the merge gate exists (`tools/autonomy/merge_gate.py` is on `main`)
1. Run `.venv/bin/python -m tools.autonomy.merge_gate --wp $ARGUMENTS --dry-run` and read its table.
2. Exit code 2 (branch behind `main`): merge `origin/main`, push, wait for CI, then re-audit only if the merge brought changes into files the WP touches; otherwise run the gate again.
3. Exit code 3 (a criterion failed): fix what it names through the normal loop. Never edit the audit report, a status fragment or a spec to satisfy the gate.
4. All criteria PASS: run the gate without `--dry-run`. It merges through GitHub's REST endpoint, pinned to the audited head.
5. Exit code 4 with 401 or 403 is an ACCESS blocker; other API errors get one retry, then the ladder.

Never merge any other way: no `gh pr merge`, no merge API call of your own, no push to `main`. The hooks block those.

## Interim, before WP-1.0 installs the gate
1. Check the same criteria by hand (`docs/process/AUTONOMY.md`, "Merge gate") and record each with its evidence in `docs/progress/$ARGUMENTS/EVIDENCE.md`.
2. Set the status fragment to MERGE-READY, push, and raise one blocker: class KIT, "interim merge: merge PR #<n> on GitHub", steps of at most 3 lines.
