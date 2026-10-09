# AQIS Lab — Operator guide (operating model v2)

This guide is for you, the owner. Claude reads the other files. Under v2 you set the bar and provide capabilities; Claude runs every step, including audits and merges, and asks you only for something in one of six classes: ACCESS, COMPUTE, EXTERNAL-AI, DECISION, PHYSICAL, KIT.

## 1. One-time setup (about 1 hour, plus WP-1.0's requests)

### 1.1 Close Phase 0
1. In PR #10 (WP-0.9), record F12 as DEBT-034 as the audit recommends, then merge the pull request.
2. In `docs/progress/BLOCKERS.md` on `main`, BLK-010 still reads `STATUS: OPEN` although WP-0.7 merged. Fill in its owner answer (the narrowed approval you gave) and set `STATUS: RESOLVED`. A stale open blocker keeps the v3 stop gate quiet about known problems.

### 1.2 Upload kit patch 4 to `main`
1. Unzip the patch. In Windows File Explorer turn on **View → Show → Hidden items** so `.claude` is visible.
2. On GitHub, branch `main`: **Add file → Upload files**; drag in everything inside the unzipped folder except `APPLY_PATCH_4.md`; commit message `Apply AQIS kit patch 4 (operating model v2)`; **Commit directly to the main branch**.
3. Delete the old rule: open `.claude/rules/10-stop-and-ask.md` on `main` → the bin icon → commit to `main`.
4. Check that `.claude/agents/` now holds 8 files and `.claude/skills/` 9 folders.

### 1.3 Self-test (new cloud session on `main`, environment `aqis-lab`, about 5 minutes)
Paste:
```text
Kit self-test v4. Report each result; change nothing and do not commit.
1. List the skills and subagents you can see from this repository.
2. Run /context and report the total tokens used by system prompt, memory files, skills and agents.
3. Try to add one comment line to CLAUDE.md with your edit tool. Report what happened.
4. Try to create docs/specs/phase-1/test.md. Report what happened.
5. Try to add a blank line to any existing file in vad_adapters with your edit tool. Report what happened.
6. Create tests/aqis_lab/selftest_tmp.txt containing "ok", then delete it.
7. Say which rule files loaded at startup and whether 60-outsourcing and 70-kit-staging did (they should not, until matching files are touched).
```
Expected: steps 3 to 5 are blocked with `BLOCKED:`; step 6 works; step 1 lists the 9 skills and 8 agents; step 2 is under about 8,000 tokens for the kit's part.

### 1.4 Cloud environment `aqis-lab` (claude.ai/code → environment selector → settings icon)
1. **API credentials → Add credential**:
   - Gemini: Name `Gemini API`; Allowed websites `generativelanguage.googleapis.com`; Custom header Name `x-goog-api-key`, clear the Prefix, paste the key as Value → Connect.
   - Hugging Face: Name `Hugging Face`; Allowed websites `huggingface.co`; header `Authorization`, Prefix `Bearer`, paste the token → Connect.
   Claude never sees these keys; the proxy attaches them. Never put keys in environment variables.
2. Keep network access **Custom** with the default package list ticked, plus the domains already there.
3. Optional, only if you add the `pyright-lsp` plugin to the Project: append `npm install -g pyright` to the setup script.

### 1.5 Gemini key (paid tier, about 10 minutes)
In Google AI Studio create an API key in a Google Cloud project with billing enabled, and set a budget alert of $10 a month in Google Cloud Billing. Check Google's current Gemini API terms: paid-tier prompts should not be used to improve Google's products. Do not use a free-tier key for company code.

### 1.6 GitHub
1. Confirm the Claude GitHub App is installed on the repository (github.com/apps/claude → Configure). Projects and routines need it.
2. Optional extra defence: branch protection on `main` needs a paid GitHub plan for a private repository. The main-guard workflow flags unexpected commits either way.

### 1.7 The Project (claude.ai/code → Projects)
1. New project: repository = this one only; environment = `aqis-lab`.
2. Project settings → General: **Thread model** Sonnet, **Thread effort** high; **Coordinator model** Sonnet, **Coordinator effort** low.
3. Project settings → Memory → Project instructions: paste the text of `docs/process/PROJECT_INSTRUCTIONS.md` (from the heading's next line).
4. Optional: Project settings → Plugins → add `pyright-lsp` (see 1.4 step 3).
5. If Projects is not in your sidebar yet, join the waitlist and use manual mode: one cloud session per WP, message `/wp-run WP-x.y`, at most 2 at a time.

### 1.8 Connectors
claude.ai connectors are offered to every cloud session. In claude.ai settings, turn off the ones the lab never uses, so threads do not carry their tool definitions.

### 1.9 Optional: Oracle runner (about 15 minutes)
GitHub → repository Settings → Actions → Runners → **New self-hosted runner** → Linux, ARM64 → run the shown commands on the Oracle VM, adding the label `oracle`. Then Settings → Secrets and variables → Actions → **Variables** → New variable `AQIS_HEAVY_RUNNER` = `oracle`. Heavy CI jobs then run there.

## 2. Running WP-1.0 (the first v2 work package)
1. Tell the Project coordinator: `Run WP-1.0`. In manual mode, start a session on `main` with `/wp-run WP-1.0`.
2. Expect these requests, each as a blocker with exact steps:
   - **EXTERNAL-AI**: start Jules for WO-1.0-01, later WO-1.0-02. At jules.google, connect GitHub, choose the repository and the branch the blocker names, and paste: `Implement docs/outsourcing/orders/WO-1.0-01.md exactly as written. Read docs/process/outsourcing/FOUNDATION.md first. Write only the files it lists, run its verify command until it passes, and open a pull request on branch wo/WO-1.0-01.` (Paste channel instead: the blocker gives the AI Studio steps.)
   - **ACCESS**: the Gemini credential, if 1.4 is not done.
   - **KIT (interim merge)**: merge the WP-1.0 pull request when Claude marks it MERGE-READY. This is the last manual merge.
   - **KIT (install)**: copy every file under `kit-staging/.claude/` on `main` into `.claude/` (same relative paths) with **Add file → Upload files**, commit to `main`, then run the self-test again (1.3). Claude then confirms parity and closes the blocker.

## 3. Daily (5 to 15 minutes)
Open the Project's Overview, or `docs/progress/OWNER_QUEUE.md` on `main`. Work through the items top down: each names its class, gives at most 7 steps and says how long it takes.

## 4. Weekly (about 20 minutes)
1. **Decision digest**: the owner queue lists new decision records. Open any you doubt; to veto one, tell the coordinator `Veto DEC-x.y-nn: <reason>`.
2. **Usage note**: claude.ai → Settings → Usage. Note the weekly percentage in one line in the Project conversation, so the yardsticks have data.
3. **Batched checks**: if post-merge owner-run checks are queued, run the batched Colab notebook the queue names and let it commit its reports.

## 5. Controls you have
- `budget low` to the coordinator: running threads finish, none start.
- `pause`: threads stop at their next safe point.
- `Run at most N threads`: change the parallel limit.
- `Run WP-x.y next`: reorder.

## 6. Troubleshooting
| Symptom | What to do |
| --- | --- |
| A blocker names a blocked host | Add exactly that host to the environment's allowed domains; sessions follow within about a minute |
| The relay exits 7 (credential) | Check the Gemini credential's host and header (1.4); the environment list should not mark it "Not sent" |
| An agent fails on `claude-haiku-5-5` | Edit that file under `.claude/agents/` and change the model to `haiku` |
| The merge gate exits 4 with ACCESS | Reconnect GitHub for Claude Code, or check the Claude GitHub App's repository access |
| A thread reports a loop-guard block | It must cite the loop ID in a blocker; answer the blocker, or tell the thread to change strategy |
| Projects is unavailable | Manual mode (1.7 step 5) |
| Something broke on `main` | Revert the merge commit on GitHub; tell the coordinator, which opens a fix WP |
