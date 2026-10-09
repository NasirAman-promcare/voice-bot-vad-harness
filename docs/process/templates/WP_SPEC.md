# WP-<x.y> — <title>

- **Depends on**: <WP IDs that must be MERGED>
- **Risk tier**: <T1 | T2 | T3>
- **Size**: <S | M | L>
- **Thread model**: <Opus high | Sonnet high>
- **Runs on**: <cloud VM, CI, Oracle runner, Colab, automated GPU>
- **Touches**: <path globs this WP may change>
- **Produces / Consumes**: <contracts, packs, artefacts>
- **Read first**: <files and blueprint sections>

## Goal
<One paragraph.>

## Deliverables
- <files, commands, documents>

## Functional requirements
- **FR-x.y-01** <testable statement>

## Non-functional requirements
- **NFR-x.y-01** <testable statement with a workload it can be measured on>

## Acceptance commands
- **AT-x.y-01** <command and expected result>

## Allowed guarded edits
- <path or pattern, or "None">

## Owner needs
| Capability class | What | When |
| --- | --- | --- |

## Owner-run checks
| Check | Blocking or post-merge | Where | Command | Expected output |
| --- | --- | --- | --- | --- |

## Outsourcing candidates
- <parts suited to work orders, or "None">

## Stop and ask if (DECISION triggers)
- <conditions under which the builder must ask rather than decide>

## Must-catch behaviours
1. <behaviour that a test and a break recipe must protect>
