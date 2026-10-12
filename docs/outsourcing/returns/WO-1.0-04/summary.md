# Summary: QUESTIONS

## Accepted Parts
| label | files | attempts | model | provider | tokens_in | tokens_out | seconds_waited |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | tools/progress/__init__.py, tests/aqis_lab/progress/__init__.py, tools/progress/fragments.py, tests/aqis_lab/progress/test_fragments.py | 1 | moonshotai/kimi-k3 | nvidia | 43964 | 5233 | 0.0 |

## Questions
The acceptance test expects a blocker whose `## BLK-…` file contains `Owner capability: legacy` to fail lint, but the work order (B12, B8) says `Owner capability: legacy` is allowed for migrated fragments and `migrate` writes exactly that. Which rule holds?
The acceptance test expects a decision fragment whose `Choice` line is `Choice: 1. A` to pass lint, but the decision template in `DECISION.md` shows `Choice: <option number and one-line summary>` on a labelled line, and the fragment parser treats `Choice: 1. A` as a labelled line, not free text. Should the parser treat `Choice`, `Why`, and `Reversal` as labelled lines?

