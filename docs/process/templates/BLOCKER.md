Blocker fragment: one file per blocker at `docs/progress/blockers.d/BLK-<WP>-<nn>.md`. The lint (from WP-1.0) checks every labelled line below.

```markdown
# BLK-<WP>-<nn> — <short title>
Status: OPEN
WP: <WP-ID>
Owner capability: <ACCESS | COMPUTE | EXTERNAL-AI | DECISION | PHYSICAL | KIT>
Raised: <YYYY-MM-DD>
Session: <link>
Unblocks: <WP IDs or parts that wait on this>
Time needed: <minutes>
Loop: <LOOP-id if the loop guard sent you here, else none>

What I need: <one sentence>

Why: <which requirement or step depends on it>

What I tried:
- <command> → <result>

Options:
1. <option> — <trade-off> (recommended)
2. <option> — <trade-off>

Exact steps:
1. <a step the owner can follow as written>
2. <at most 7 steps>

Meanwhile: <what you keep doing that does not depend on the answer>

Owner answer: <filled in when resolved; then set Status: RESOLVED>
```
