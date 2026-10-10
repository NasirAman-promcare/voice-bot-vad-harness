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
   - Mistral (1.5 step 3): Name `Mistral`; Allowed websites `api.mistral.ai`; header `Authorization`, Prefix `Bearer`, paste the key → Connect.
   - Hugging Face: Name `Hugging Face`; Allowed websites `huggingface.co`; header `Authorization`, Prefix `Bearer`, paste the token → Connect.
   Claude never sees these keys; the proxy attaches them. Never put keys in environment variables.
2. Keep network access **Custom** with the default package list ticked, plus the domains already there.
3. Optional, only if you add the `pyright-lsp` plugin to the Project: append `npm install -g pyright` to the setup script.

### 1.5 Model pool: Gemini and Mistral keys (about 20 minutes)
The relay spreads work over a pool of models, each with its own quota, listed in `config/aqis_lab/model_pool.json`. Its figures are copied from your own pages: Gemini from AI Studio (9 October 2026: six Flash models at 20 requests a day each, two Flash-Lite at 500) and Mistral from Admin → Limits (10 October 2026: Codestral 25.08, Mistral Large 25.12 and Ministral 14B, no daily cap). Only you can edit that file.
1. **Gemini**: in Google AI Studio create **one** API key in your project and add it as the Gemini credential (1.4 step 1). Use no other Google account or project for the lab: extra keys in one project share its limits, and spreading work over several accounts or projects to get more free quota breaks Google's API terms and risks suspension of the whole Google account.
2. **Mistral** (done: organization `promcaresolution` exists): in **Admin → Privacy**, make sure **Anonymous improvement data** is switched off, so your code is not used for training. In **API Keys**, create a key.
3. In the `aqis-lab` environment: **API credentials → Add credential**, Name `Mistral`, Allowed websites `api.mistral.ai`, header `Authorization`, Prefix `Bearer`, paste the key → Connect. If network access is Custom, add `api.mistral.ai` to the allowed domains.
4. Mistral is already enabled in the pool file with your limits. Edit the file only if Admin → Limits changes; never add a model with fewer than about 60,000 tokens a minute (Mistral Medium, Large 4 and Small have 20,000, below one request). Keep `share` equal to the Project's thread limit (2 by default).
5. After WP-1.0, Claude runs the relay with `--models`, which checks every model name against Gemini's and Mistral's own lists; it raises an item only if a name needs changing.
6. Know the trade-off: on Gemini's free tier Google may use what the relay sends (lab tooling, specs and tests, never secrets, personal data or client data) to improve its products, and human reviewers may read it. If that is not acceptable for this code, enable billing on the same Google project and change `tier` to `paid` with the paid limits.

Optional providers, already in the pool file but switched off: NVIDIA's API catalog (build.nvidia.com; large free volume, but its trial terms allow testing and evaluation only and let NVIDIA use what you send) and OpenRouter (50 free requests a day, 1,000 after a one-time $10 top-up; its free models are weaker). Each is turned on the same way as Mistral: a key, a credential for its host, `"enabled": true`.

Daily quotas reset at midnight Pacific time for Gemini (12:00 in Pakistan until 1 November 2026, 13:00 after) and at midnight UTC (05:00 in Pakistan) for the others. When one model runs out, the relay moves to the next; it pauses only when every eligible model is used up, and Claude resumes it after the reset.

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
   - **EXTERNAL-AI**: start two Jules tasks at once, for WO-1.0-01 and WO-1.0-10; later one for WO-1.0-02, then one for WO-1.0-11. At jules.google, connect GitHub, choose the repository and the branch the blocker names, and paste (with the order's number): `Implement docs/outsourcing/orders/WO-1.0-01.md exactly as written, one step at a time in the order of its steps list. Read docs/process/outsourcing/FOUNDATION.md first. Write only the files it lists, run its verify command until it passes, and open a pull request on branch wo/WO-1.0-01.` (Paste channel instead: the blocker gives the AI Studio steps.)
   - **ACCESS**: the Gemini credential, if 1.4 is not done; Mistral, if 1.5 is not done (the relay also works on Gemini alone).
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
| A thread is `WAITING: pool reset` | Nothing: it resumes after the reset. If it happens most days, start whole orders in Jules, or consider the paid tier (1.5 step 6) |
| The relay prints `POOL: remove or rename <model>` | That model is not offered on your tier or its name changed: remove its entry from `config/aqis_lab/model_pool.json`, or correct the name from the `--models` output |
| The relay prints `ACCESS: add or fix the <provider> credential` | Check that provider's credential host and header (1.4); the relay carries on with the other providers meanwhile |
| Claude reports a provider is unverified | Check its limits in that provider's console and set `verified_on` in the pool file (1.5 step 4) |
| An agent fails on `claude-haiku-5-5` | Edit that file under `.claude/agents/` and change the model to `haiku` |
| The merge gate exits 4 with ACCESS | Reconnect GitHub for Claude Code, or check the Claude GitHub App's repository access |
| A thread reports a loop-guard block | It must cite the loop ID in a blocker; answer the blocker, or tell the thread to change strategy |
| Projects is unavailable | Manual mode (1.7 step 5) |
| Something broke on `main` | Revert the merge commit on GitHub; tell the coordinator, which opens a fix WP |
