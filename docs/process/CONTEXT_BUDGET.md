# Context budget, navigation and the compute map

## Fixed context (re-sent every turn)
Budget: about 8,000 tokens, checked with `/context` at session start.

| Item | Budget |
| --- | --- |
| `CLAUDE.md` | under 200 lines (now about 50) |
| Unscoped rules (`.claude/rules/00` to `50`) | short; about 105 lines in total |
| Path-scoped rules (`60`, `70`) | load only when matching files are touched |
| Skill and agent descriptions | 1 to 2 lines each |
| MCP servers in the repo | none |
| claude.ai connectors | offered to every cloud session; the owner turns off unused ones |

## Navigation
1. `docs/index/MAP.md`: one line per module (purpose, capabilities, owning WP).
2. `docs/index/SYMBOLS.md`: public symbols with `file:line`. `docs/index/CALLERS.md`: who imports a module. `docs/index/TESTMAP.md`: requirement ID to tests to modules.
3. Exact line ranges. Broad search only for what the map lacks, delegated to `Explore`.
4. `docs/guides/<subsystem>.md` (written by Gemini, stale-marked by CI when their source hashes change): read one instead of many files when entering an unfamiliar area.
5. LSP: if the Project loads the `pyright-lsp` plugin (and the setup script installs `pyright`), prefer go-to-definition and find-references over search.

## Output hygiene
- `pytest -q --tb=short`; full logs to `/tmp`, read with `grep` or `tail`, or through `log-digest`.
- Affected tests while building (`python -m tools.index impact`); the full fast suite before audit; everything else in CI.
- Never `cat` a large file or a whole log; never paste CI logs.

## Session hygiene
- A new thread for new work; prompt caching lasts about an hour, and reviving an old thread re-reads all of it.
- No scheduled check-ins, no polling, no watching pull requests after merge, no chatty messages between sessions.
- Compact at natural boundaries with a focus line.

## Compute map
| Work | Where |
| --- | --- |
| Coding, fast tests | Claude cloud VM (4 vCPU, 16 GB RAM, 30 GB disk, x86-64) |
| Full suites, break suite, mutation, index and progress generation | GitHub Actions; heavy jobs on the Oracle self-hosted runner when the repository variable `AQIS_HEAVY_RUNNER` names it |
| CPU data jobs | Oracle runner (Arm A1; x86-only packages such as TEN VAD stay on x86 runners) |
| A Claude session needing a big disk or local data | Claude Code on the Oracle VM through Remote Control (a Project can run a thread there) |
| GPU with the owner | Colab Plus, batched notebooks |
| GPU without the owner | Kaggle API or Modal, after a probe file and parity test; AWS EC2 GPU spot as a burst option |
