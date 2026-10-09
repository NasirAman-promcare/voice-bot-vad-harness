Decision record: one file per decision at `docs/progress/decisions.d/DEC-<WP>-<nn>.md`. Use it for choices inside the spec's intent instead of asking the owner. The owner reviews new records weekly and may veto.

```markdown
# DEC-<WP>-<nn> — <short title>
Status: ACTIVE            (ACTIVE | VETOED | SUPERSEDED by DEC-...)
WP: <WP-ID>
Date: <YYYY-MM-DD>
Spec basis: <requirement IDs and the sentence of the spec that makes this a choice within its intent>

Question: <what had to be decided>

Options:
1. <option> — <consequences>
2. <option> — <consequences>

Choice: <option number and one-line summary>

Why: <evidence: commands, measurements, documentation links>

Cannot-do check (all must be "no"):
- Weakens, skips or deletes a test: no
- Changes a requirement, threshold or exit criterion: no
- Touches a NEVER path: no
- Adds synthetic or substitute data where real data is required: no
- Widens network, credentials or security permissions: no
- Spends money or starts a paid service or trial: no

Reversal: <what a veto would take to undo>
```
