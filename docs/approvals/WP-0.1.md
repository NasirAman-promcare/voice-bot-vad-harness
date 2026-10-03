STATUS: APPROVED
WP: WP-0.1
APPROVED-BY: owner
DATE: 2026-10-03
PLAN: docs/progress/WP-0.1/PLAN.md
CONDITIONS:
- Questions 1 to 6: as recommended in PLAN.md, with the specifics below.
- Question 1: a new full Tier 2 run with today's harness, captured with the plan's owner steps, with the old results moved aside first.
- Question 6: report negative and null latencies exactly as recorded, with counts. SUMMARY.md also carries this note, labelled as the owner's statement: "Negative wall-clock pipeline latencies are a known measurement artefact. The harness estimates when a sample arrived by counting forward at the nominal rate from the first packet, while audio arrives in 20 ms packets, so decisions can look up to about one packet early, plus some arrival jitter. They are not real. Fixing the calculation is harness work outside this WP." Add a row to docs/progress/DEBT.md: compute wall-clock latency from the arrival time of the packet that carried each sample; target: the Phase 2 VAD timing work.
- R6: if the report's summary table shows an "orchestrator" row, it is the run-context record listed as an adapter, a known reporting quirk. It is not an operating point. Record it and do not count it.
