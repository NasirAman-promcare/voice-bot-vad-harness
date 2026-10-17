# Archive: operating model v2 (kit patch 4) and WP-1.0

**Status:** retired on 17 Oct 2026 by the results-first reset (Claude Doc "AQIS Lab — Results-first reset"). Nothing here is in force. Do not read or reuse it unless the owner asks.

## What was archived
- **Kit patch 4 ("operating model v2"), applied to `main` on 9–10 Oct 2026:**
  - `CLAUDE.md` v2;
  - the rules `00` to `70`;
  - 9 skills (`wp-run`, `wp-merge`, `wo-write` and others) and 8 agents;
  - `docs/process/` additions (AUTONOMY, ESCALATION, PARALLEL, MODEL_ROUTING, CONTEXT_BUDGET, PROJECT_INSTRUCTIONS, templates);
  - the outsourcing foundation and the work orders `docs/outsourcing/orders/WO-1.0-01` to `-11`;
  - the spec `docs/specs/phase-1/WP-1.0-operating-model-v2.md`;
  - `config/aqis_lab/model_pool.json` (Gemini, Mistral and later NVIDIA limits).
- **WP-1.0 (tooling for v2), never merged:**
  - the relay, governor and router over a model pool;
  - the merge gate, the Lab Map and capability registry tooling;
  - the break suite;
  - progress fragments and the hook update;
  - about 290 files and 24,800 added lines, still IN-BUILD on 12 Oct 2026.

## Where it lives
| Ref | What it holds |
| --- | --- |
| branch `archive/operating-model-v2` | `main` as it was before the reset, with the v2 kit in place (head `da75708`, 12 Oct 2026) |
| branch `claude/wp-1-0-operating-model-v2` | WP-1.0 work in progress (head `a4e83f5`); handover in `docs/progress/status.d/WP-1.0.md` on that branch |
| branches `wo/WO-1.0-*` | the outsourced work orders and their fix rounds |

To read a file without switching branches, run `git show archive/operating-model-v2:<path>`.

## Why it was retired
A month went into process tooling and no model had been measured yet. The reset keeps what produced value:
- Phase 0's scorer, mixer, results store, unit log, Colab launcher pattern and hooks;
- the VAD harness and the Tier 2 Jitsi path.

Work now runs as one-week sprints that end in model scorecards; see `CLAUDE.md` and `docs/specs/sprints/`.

## Possibly useful later
- The streaming NVIDIA client from WP-1.0 (DEC-1.0-09) and the measured provider limits in `model_pool.json`, if an LLM API is needed again.
- The kit patch 4 operator guide, as a record of the free-tier limits checked in October 2026.
