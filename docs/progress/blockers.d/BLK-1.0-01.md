# BLK-1.0-01 — Start Jules for the bootstrap orders (wave 1 done; now wave 2 and FIX-1 of WO-1.0-10)
Status: OPEN
WP: WP-1.0
Owner capability: EXTERNAL-AI
Raised: 2026-10-10
Session: https://claude.ai/code/session_01MdrFmVCBzGrRzg4n2dVGRx
Unblocks: WP-1.0 (FR-1.0-01, FR-1.0-14; then wave 2 WO-1.0-02 and wave 3 WO-1.0-11, raised as later items of this blocker)
Time needed: 3 minutes now (two tasks); about 1 minute for wave 3
Loop: none

What I need: start two Jules tasks against the WP-1.0 branch: WO-1.0-02 (wave 2) and FIX-1 of WO-1.0-10. They touch disjoint files and can run at once.

Wave 1 history: the owner started both tasks (PRs #11 and #12). Claude reviewed them and merged them into the WP branch (`1da4b3e`, `ad5f769`).

Why: FR-1.0-13 says the four bootstrap orders go through Jules or the paste channel, because the relay is what they build. Claude cannot reach Jules.

What I tried:
- Committed both orders' acceptance tests: `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_01.py` and `test_acceptance_wo_1_0_10.py`.
- Ran `.venv/bin/python -m pytest tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_01.py tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_10.py -q`. All 94 tests fail with `ModuleNotFoundError: No module named 'tools.outsourcing'`, the expected reason.
- Added each order's B12 or B14, pinning the interface details the tests use.

Options:
1. Jules, two tasks at once (about 1 minute of owner time each) — the order's own channel. (recommended)
2. The paste channel through AI Studio — about 5 minutes per step, 14 steps for the two orders.

Exact steps:
1. Open https://jules.google.com, choose NasirAman-promcare/voice-bot-vad-harness, branch `claude/wp-1-0-operating-model-v2`.
2. Start a task with: `Implement docs/outsourcing/orders/WO-1.0-02.md exactly as written, on branch wo/WO-1.0-02. Open the pull request against claude/wp-1-0-operating-model-v2, not main.`
3. Start a second task with: `Apply the fix order docs/outsourcing/returns/WO-1.0-10/FIX-1.md exactly as written, on branch wo/WO-1.0-10-fix-1. Open the pull request against claude/wp-1-0-operating-model-v2, not main.`
4. If Jules asks a question, answer only "Follow the order; if it is unclear, write the question into the pull request description and stop." Do not merge anything.
5. When both pull requests are open, tell this session "wave 2 PRs are open". Wave 3 (WO-1.0-11) follows once both are merged.

Meanwhile: I write the acceptance tests for WO-1.0-02 and WO-1.0-11 (waves 2 and 3) and WO-1.0-03 to WO-1.0-09. I also do the pre-send amendments of WO-1.0-03, -04, -07 and -09, fix DEBT-033 and DEBT-034, and add the requirement tests. When the pull requests are open, I check their scope, merge them into the WP branch and write the break recipes.

Owner answer:
