# WP-0.8 — Consent, recording guide, filler library v0 and targets

- **Depends on**: none
- **Runs on**: documents only
- **Read first**: AQIS Test Lab blueprint sections "Test data strategy" and "Voice emotion and the filler selector"; Build Plan sections "Dataset architecture" and "Phase 1"

## Goal
Prepare everything people-facing that phase 1 needs, and put the owner's decisions on record.

## Deliverables
- `docs/recording/CONSENT_FORM.md`, `docs/recording/RECORDING_GUIDE.md`, `docs/recording/SESSION_FORM.md`
- `docs/fillers/FILLER_LIBRARY_v0.md`
- `docs/decisions/TARGETS_OPTIONS.md`

## Functional requirements
- **FR-0.8-01** Consent form in plain English, one page: purpose, what is recorded, how it is stored, who can access it, retention period (a blank for the owner to fill, never an invented value), right to withdraw, and contact.
- **FR-0.8-02** Recording guide for campaign A: the 80-prompt structure by family, device and room guidance, file naming, format, transfer, and quality checks, matching the Build Plan.
- **FR-0.8-03** Session form: speaker ID, device, room, noise source, accent group, consent reference.
- **FR-0.8-04** Filler library v0: about 20 fillers across the four risk levels, each with an ID, text, intended use and contexts where it must never play.
- **FR-0.8-05** Targets options: for the harm-rate target, the practical margin for model comparisons, the timing budget and the gate escalation limit, give 2 or 3 options each with trade-offs, citing the blueprint. The owner decides by approval file; the WP does not choose.

## Acceptance
- **AT-0.8-01** The auditor checks completeness against each requirement and that no value was invented where the owner must decide.

## Must-catch behaviours
1. No value the owner must decide is filled in by Claude.
2. Every filler has a risk level and at least one context where it must never play.
