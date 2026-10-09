# Parallel work

Work packages run in parallel as threads of a Claude Code Project, in waves planned from each phase's dependency graph. Parallel threads share one usage budget: parallelism shortens elapsed time only when tokens per WP fall and owner waits disappear.

## The dependency graph (in each phase overview)
One row per WP:

| Field | Meaning |
| --- | --- |
| WP | ID and title |
| Depends on | WPs that must be MERGED first |
| Touches | Path globs the WP may change (the only paths its plan may budget) |
| Produces / Consumes | Contracts, packs and artefacts it creates or uses |
| Tier / Size | T1, T2 or T3; S, M or L |
| Thread model | Opus or Sonnet, with effort |
| Owner needs | Capability classes and timing |
| Compute | Cloud VM, CI, Oracle runner, Colab, automated GPU |

Rules:
- A WP is **ready** when its dependencies are MERGED and its Touches overlap no running WP's Touches.
- WP-x.0 of each phase is the contracts WP: it freezes shared interfaces as real code with contract tests. A contract change later is its own WP.
- Generated files (`docs/index/*`, the progress tables, the registry) are never in any WP's Touches; CI regenerates them on `main`.

## Running a wave in a Project
1. Project settings: repository = this repo only; environment = `aqis-lab`; thread model Sonnet at high effort; coordinator Sonnet at low effort; instructions = `PROJECT_INSTRUCTIONS.md`.
2. Tell the coordinator: "Run Phase N wave A" or "Run the ready WPs".
3. It starts one thread per ready WP with `/wp-run WP-x.y`, at most the number of threads you set (default 2), setting each thread's model from the graph.
4. Threads that hit the usage limit resume on their own when it resets; the coordinator starts the next ready WP when a thread reports MERGED.

## Without Projects (not yet rolled out to the account)
Start one cloud session per ready WP from claude.ai/code on branch `main` with environment `aqis-lab`, each with the message `/wp-run WP-x.y`. The same repo files coordinate them; you are the coordinator, so keep to 2 at a time.

## Budget arithmetic
- Threads draw on one budget: N threads reach the 5-hour limit in roughly 1/N of the time.
- Pro-level budgets: about 2 threads at once. Max-level budgets: 3 to 4.
- The gain comes from filling waits (CI, Colab, Gemini, the owner) and from threads resuming across usage windows by themselves.
- Agent teams (about 7 times the tokens) and chatty cross-session messages are not used.

## Conflicts
- Fragments and WP-prefixed IDs prevent conflicts in records.
- The merge gate requires a fresh base: a WP that falls behind `main` merges `origin/main`, re-runs CI, and is re-audited only if the incoming changes touch its files.
- A real code conflict between two WPs means their Touches overlapped: the coordinator pauses the later one and records the lesson in project memory.
