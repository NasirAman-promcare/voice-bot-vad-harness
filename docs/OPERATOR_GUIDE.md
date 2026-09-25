# AQIS Lab — Operator guide for Phase 0 with Claude Code

This guide is for you, the owner. Claude Code reads the other files; you run the process.

## How the kit keeps Claude honest

| Layer | What it is | What it stops |
| --- | --- | --- |
| Instructions | `CLAUDE.md`, `.claude/rules/`, one spec per work package, six project skills | Vague tasks, silent shortcuts, scope drift |
| Hard enforcement | An edit guard hook, permission deny rules, and a stop gate that runs every time Claude finishes a turn | Edits to protected files, forged approvals, weakened or deleted tests, stubs, placeholders, swallowed errors, failing tests at hand-off |
| Independent checks | An auditor subagent at `xhigh` effort that never sees the builder's conversation, mutation spot-checks, GitHub CI, and your approval before any code | Self-grading, tests that pass without testing anything, "works on my machine" |

Instructions alone can be ignored; the hooks cannot. Claude Code runs a repository's `CLAUDE.md`, `.claude/rules/`, skills, agents, and the hooks and permission rules in `.claude/settings.json` in cloud sessions, as long as the session has a single repository.

## 1. Decisions already made

- **Same repository.** The lab reuses harness parts, Colab clones one repository, and cloud sessions only run a repository's hooks when the session has one repository. The protected-path list keeps the harness safe.
- **You own the rules.** Only you edit `CLAUDE.md`, `.claude/`, `docs/specs/`, `docs/process/` and `docs/approvals/`, always on `main` through the GitHub website.
- **One work package (WP) per branch and pull request.** Only you merge.

## 2. Arrange everything first

| # | Item | How | Needed by |
| --- | --- | --- | --- |
| 1 | Tag the current state | GitHub → Releases → Draft a new release → tag `pre-aqis-baseline` on `main` → Publish | Before the kit |
| 2 | Optional third-party skills | Section 4 | Before the kit upload |
| 3 | Upload the kit to `main` | Section 3 | Everything |
| 4 | Cloud environment `aqis-lab` | Section 5 | First session |
| 5 | Colab probe | `docs/environment/README.md` → `colab_probe.txt` | WP-0.0 |
| 6 | Oracle probe | `docs/environment/README.md` → `oracle_probe.txt` | WP-0.6 |
| 7 | Ten smoke recordings | Record 10 clips of 3 to 8 s on your phone in a quiet room, reading 5 digit strings and 5 short questions. Upload to `data/owner_smoke/` with `transcripts.csv` (columns `file,text`) and a `CONSENT.md` line saying you agree to lab use | WP-0.4 |
| 8 | Drive folder | Create `AQIS_LAB` in My Drive | WP-0.5 |
| 9 | GitHub token for Colab | GitHub → Settings → Developer settings → Fine-grained tokens → read-only "Contents" access to this repository only. In Colab, open the key icon (Secrets), add `GITHUB_TOKEN`, allow notebook access | WP-0.5 |
| 10 | Phone notifications | Install the Claude app, sign in, allow notifications; cloud sessions can be monitored from it | First session |
| 11 | Usage check | claude.ai → Settings → Usage: see your plan usage and usage credits | First session |
| 12 | Kit self-test | Section 9 | Before WP-0.0 |

## 3. Upload the kit with the GitHub website

1. Unzip the kit on your computer. In Windows File Explorer, turn on **View → Show → Hidden items** so the `.claude` folder is visible.
2. On GitHub, open the repository on branch `main` → **Add file → Upload files**.
3. Drag everything inside the unzipped folder (including `.claude`, `CLAUDE.md` and `docs`) into the page.
4. Commit message: `Add AQIS lab Phase 0 kit`. Choose **Commit directly to the main branch**.
5. Check that `.claude/settings.json` and `.claude/hooks/stop_gate.py` appear in the repository. If the `.claude` folder did not upload, upload its files again from inside that folder, using **Create new file** with the path typed as `.claude/...`.

## 4. Skills

**Project skills (included).** Type these in the session:

| Command | What it does | Effort it runs at |
| --- | --- | --- |
| `/wp-start WP-x.y` | Reads the spec and writes a full plan; changes no code; stops for your approval | xhigh |
| `/wp-build WP-x.y` | Builds the approved plan test-first, with evidence | high |
| `/wp-audit WP-x.y` | Independent audit by the auditor subagent | xhigh |
| `/surgical-fix <finding IDs>` | Fixes only what is broken, without touching anything else | high |
| `/phase-audit 0` | Full end-of-phase audit | xhigh |
| (automatic) `ask-owner` | Claude uses it by itself whenever it is blocked | session level |

**Optional third-party skills.** [Superpowers](https://github.com/obra/superpowers) is an MIT-licensed skill set; three of its skills fit this project: test-driven development, systematic debugging and verification before completion. Cloud sessions do not install plugins that a repository declares, and `/plugin` does not work there, but they do load skill folders committed to `.claude/skills/`. To add them before uploading the kit:

1. On the Superpowers GitHub page, choose **Code → Download ZIP** and unzip it.
2. From its `skills` folder, copy `test-driven-development`, `systematic-debugging` and `verification-before-completion` into the kit's `.claude/skills/`.
3. Copy its `LICENSE` file to `.claude/skills/_third_party/superpowers-LICENSE.txt`.

The kit's rules take priority over any third-party skill. If a copied skill mentions another Superpowers skill you did not copy, Claude ignores that mention.

**Bundled skill worth using.** Before merging a larger work package, you can type `/code-review` for a second opinion on the branch.

## 5. Cloud environment `aqis-lab`

At claude.ai/code, click the cloud icon above the message box → **Add cloud environment**:

- **Name**: `aqis-lab`
- **Network access**: **Custom**; tick **Also include default list of common package managers**; allowed domains:
```text
alphacephei.com
openslr.org
*.openslr.org
huggingface.co
*.huggingface.co
*.hf.co
```
- **Environment variables**: none. Never put secrets here; anyone using the environment can read them.
- **Setup script**:
```text
#!/bin/bash
apt-get update -y >/dev/null 2>&1 || true
DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg sox libsndfile1 rclone git-lfs libc++1 libopus0 >/dev/null 2>&1 || true
exit 0
```

Pick `aqis-lab` in the selector before every session. When Claude reports a blocked host, add exactly that host and start a new session; the environment rebuilds after a change to its hosts or script.

## 6. Running a work package

Start with WP-0.0. Each step:

1. **Plan.** New session: environment `aqis-lab`, your repository, branch `main`, permission mode **Auto**. Type `/effort high`, then `/wp-start WP-0.0`.
2. **Review.** Read `docs/progress/WP-0.0/PLAN.md` in the session's diff view. Answer Claude's numbered questions in the chat; it updates the plan.
3. **Approve.** On GitHub, on `main`, open `docs/approvals` → **Add file → Create new file** named `WP-0.0.md`. Paste `docs/process/templates/APPROVAL.md`, fill it in, add any `ALLOW-` lines the spec asks for, and commit to `main`.
4. **Build.** In the same session, or a new one started on the plan's branch, type `/wp-build WP-0.0`. Wait for `✅ READY FOR AUDIT` or `🛑 OWNER ACTION NEEDED`.
5. **Audit.** Type `/wp-audit WP-0.0`. Read `docs/progress/WP-0.0/AUDIT.md`.
6. **Fix if needed.** On FAIL, type `/surgical-fix WP-0.0-F01 WP-0.0-F02` (the finding IDs), then audit again.
7. **Owner-run checks.** Do the Colab or Oracle checks listed in the spec and `EVIDENCE.md`; commit their reports.
8. **Merge.** On GitHub, merge the pull request only when the audit says PASS, CI is green, and no blocker is open. Then set the WP to `MERGED` in `docs/progress/STATUS.md`.

Keep one WP per session. Run WP-0.1 (your Tier 2 run) and WP-0.8 (documents) alongside the main chain.

## 7. Effort level

Opus 5.5 starts at **medium** effort in Claude Code. Anthropic describes medium as reducing tokens for cost-sensitive work that can trade off some intelligence, high as balancing tokens and intelligence, and max as prone to overthinking with diminishing returns. For this project:

- Type `/effort high` at the start of every session.
- The skills raise planning and auditing to `xhigh` themselves; that is where depth pays most.
- Use `medium` only for the documents-only WP-0.8.
- Avoid `max` and `ultracode`; they spend far more for little gain here.

If `/effort` replies "Not applied", carry on; the skills still set their own level.

## 8. Usage and credits

- Cloud sessions share your plan's usage limits with the rest of your Claude use. There is no separate charge for the cloud machine.
- Credits of the kind you describe are normally spent only after your plan's included usage runs out. Check claude.ai → Settings → Usage for how yours are set, and the [usage credits article](https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans).
- To keep most of the $100 for later phases, pace Phase 0 inside your plan limits: roughly 30 sessions over about two weeks (plan, build and audit for each WP), with pauses when you near a limit.
- Savings that do not cost quality: one WP per session; no huge downloads in the cloud; skills load only when called; the stop gate runs only the fast tests; avoid Fable models, `max` and `ultracode`.

## 9. Kit self-test (first session, about 5 minutes)

Start a session on `main` with the `aqis-lab` environment and paste:

```text
Kit self-test. Do exactly these steps and report each result; change nothing else and do not commit.
1. List the skills and subagents you can see from this repository.
2. Show the output the SessionStart hook added to your context.
3. Try to add one comment line to CLAUDE.md with your edit tool. Report what happened.
4. Try to create docs/specs/phase-0/test.md. Report what happened.
5. Try to add a blank line to vad_adapters (any existing file) with your edit tool. Report what happened.
6. Create tests/aqis_lab/selftest_tmp.txt containing "ok", then delete it.
```

Expected: steps 3 to 5 are blocked with a `BLOCKED:` message; step 6 works; step 1 lists the six project skills and `wp-auditor`. If anything differs, stop and fix the kit before WP-0.0.

## 10. When Claude needs you, and when things go wrong

- **`🛑 OWNER ACTION NEEDED`**: Claude has written a blocker in `docs/progress/BLOCKERS.md` and stopped. Answer in the chat. If the session went idle, reopen it; the conversation is restored.
- **`⚠️ STOP GATE`**: the automatic check still sees problems. Do not merge. Ask Claude to fix them with `/surgical-fix`.
- **`BLOCKED:` on a harness file**: decide. If the change is truly needed, approve it with an `ALLOW-EDIT:` line for exactly that file; otherwise say no.
- **Setting up the harness anywhere** (Colab, Oracle, CI, cloud VM): once WP-0.0 round 2 is merged, run `bash aqis_lab/deploy/harness_provision.sh` first instead of manual download, extract and install cells; exact Colab cells are in `docs/colab/HARNESS_SETUP.md`.
- **A Colab or Oracle check fails**: commit the report, start a session, and type `/surgical-fix <path to the report>`. Do not debug inside Colab.
- **Something broke on `main`**: revert the pull request on GitHub, then fix on a new branch.
