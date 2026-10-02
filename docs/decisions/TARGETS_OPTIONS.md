<!-- AQIS lab WP-0.8 FR-0.8-05. Tests read the headings, option tables, citations and decision lines of this file
(tests/aqis_lab/test_aqis_targets_options.py): keep them when editing. Only the owner fills the decision lines,
in docs/approvals/WP-0.8.md, never in this file. -->
# Targets: options for the owner

For each of the four targets FR-0.8-05 names, this document gives 2 or 3 options with what each gives and what it costs, citing the committed blueprint and Build Plan (`docs/specs/sources/`).

It does not pick or rank an option: the owner decides each target. Where the blueprint gives one example value (harm rate, practical margin, timing budget), the "Source" column marks it, and the other options are values proposed here to show the range. The gate escalation options are the three rates the blueprint itself evaluates.

## How the owner decides
Add one line per target to `docs/approvals/WP-0.8.md` on `main`, naming one option ID from the tables below:

```text
DECISION: harm-rate = HR-?
DECISION: margin = PM-?
DECISION: timing-budget = TB-?
DECISION: gate-escalation = GE-?
DECISION: retention = <how long recordings are kept, in your words>
```

The retention line answers the retention blank of the consent form (`docs/recording/CONSENT_FORM.md`, FR-0.8-01). The form itself keeps its blank.

## Harm rate
The blueprint's target: "Share of fillers rated 'wrong' (such as cheerful filler to upset caller) must be strictly below target (e.g., <2%)." [Blueprint § Quantitative Targets]

The Build Plan's phase 4 filler pack has 500 rated turns [Build Plan § Phases]. Each option states how many of those 500 turns may be rated wrong for an exact one-sided binomial test to show, with 95 % confidence, that the true rate is below the target.

| Option | Value | What it gives | What it costs | Source |
| --- | --- | --- | --- | --- |
| HR-A | below 1 % | The fewest misfires reach callers; Level 2 and Level 3 fillers play only when the selector is very sure. | Hardest to show: it allows at most 1 of 500 rated turns to be wrong. More turns fall back to Level 0 or Level 1 fillers, so the bot sounds less warm. | Blueprint § Quantitative Targets; Build Plan § Phases |
| HR-B | below 2 % | A balance between warmth and misfires: more Level 2 and Level 3 fillers can play than under HR-A. | It allows at most 4 of 500 rated turns to be wrong. About 1 caller turn in 50 may still get a wrong filler. | Blueprint § Quantitative Targets; the blueprint's example value; Build Plan § Phases |
| HR-C | below 5 % | Easiest to show: it allows at most 16 of 500 rated turns to be wrong. More Level 2 and Level 3 fillers can play. | Up to 1 caller turn in 20 may get a wrong filler, such as a cheerful phrase to an upset caller. | Blueprint § Quantitative Targets; Build Plan § Phases |

**Decision:** [OWNER DECIDES: harm-rate option]

## Practical margin for model comparisons
The blueprint's rule: "Win declared only if difference interval excludes zero and gap exceeds practical margin (e.g., >=0.5 points meaning-changing error)." [Blueprint § Quantitative Targets]

The margin is in percentage points of meaning-changing error. A win needs both conditions: the interval excludes zero, and the gap is at least the margin.

| Option | Value | What it gives | What it costs | Source |
| --- | --- | --- | --- | --- |
| PM-A | 0.25 points | Smaller real improvements can count as a win, so a better model is adopted sooner. | Some declared wins may be too small for callers to notice, and each switch of model has its own cost. | Blueprint § Quantitative Targets |
| PM-B | 0.5 points | Wins need a gap callers are likely to notice, while half-point improvements still count. | Gaps between 0.25 and 0.5 points never count as a win, even when the interval excludes zero. | Blueprint § Quantitative Targets; the blueprint's example value |
| PM-C | 1.0 point | Only clear, noticeable gains count; fewer model switches. | A real but modest improvement below 1 point is never adopted on this evidence alone. | Blueprint § Quantitative Targets |

**Decision:** [OWNER DECIDES: margin option]

## Timing budget
The blueprint's target: "Estimated timing budget met on at least 90% of turns." [Blueprint § Quantitative Targets]

The budget is the blueprint's latency condition: t_final + t_gate + t_heavy + t_reply <= t_turn_end + d_filler, with filler length 0.8 to 1.5 s [Blueprint § Timing Budget]. The options set the share of turns on which it must hold.

| Option | Value | What it gives | What it costs | Source |
| --- | --- | --- | --- | --- |
| TB-A | at least 95 % of turns | Dead air after a filler is rare: about 1 turn in 20 misses the budget. | Needs faster finalisation, gating and heavy transcription, or more turns with long fillers, so fewer model set-ups pass. | Blueprint § Quantitative Targets; Blueprint § Timing Budget |
| TB-B | at least 90 % of turns | Most turns have no gap after the filler, and moderately slower models can still pass. | About 1 turn in 10 may still leave a gap after the filler ends. | Blueprint § Quantitative Targets; the blueprint's example value; Blueprint § Timing Budget |
| TB-C | at least 80 % of turns | More model set-ups pass, including slower but more accurate heavy transcription. | About 1 turn in 5 may leave a gap after the filler, which callers notice as a pause. | Blueprint § Quantitative Targets; Blueprint § Timing Budget |

**Decision:** [OWNER DECIDES: timing-budget option]

## Gate escalation limit
The blueprint's target: "Gate evaluated at 10%, 20%, and 30% escalation rate." [Blueprint § Quantitative Targets]

The gate decides, in under 50 ms, whether a turn goes to heavy transcription; the heavy turnaround must fit within the filler [Blueprint § Timing Budget]. The options are the three rates the blueprint evaluates.

| Option | Value | What it gives | What it costs | Source |
| --- | --- | --- | --- | --- |
| GE-A | 10 % of turns escalated | The least heavy-transcription work and the fewest turns that depend on the heavy turnaround fitting within the filler. | More transcription errors pass without the heavy check. | Blueprint § Quantitative Targets; Blueprint § Timing Budget |
| GE-B | 20 % of turns escalated | A middle point between correction and cost. | Twice the heavy work of GE-A, and more turns depend on the heavy turnaround. | Blueprint § Quantitative Targets; Blueprint § Timing Budget |
| GE-C | 30 % of turns escalated | The most turns get the heavy check, so the most errors can be fixed. | Three times the heavy work of GE-A; the timing budget is hardest to meet on escalated turns. | Blueprint § Quantitative Targets; Blueprint § Timing Budget |

**Decision:** [OWNER DECIDES: gate-escalation option]
