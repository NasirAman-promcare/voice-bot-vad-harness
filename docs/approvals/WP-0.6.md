STATUS: APPROVED
WP: WP-0.6
APPROVED-BY: owner
DATE: 2026-09-29
PLAN: docs/progress/WP-0.6/PLAN.md
CONDITIONS:
- Questions 1-16: as recommended in PLAN.md.
- Machine configuration: Oracle VM.Standard.A1.Flex (Ampere A1 aarch64, 4 OCPUs, 24 GB RAM). Core reservation policy: reserve highest-numbered half of physical cores (cores 2-3) for timing runs, keeping batch runs on cores 0-1.
- DEBT-008: closed in this WP.
- Round 2: fix WP-0.6-F01 (test trace with historical commit/lock hash), WP-0.6-F02 (negative tests for read-side store integrity checks), WP-0.6-F03, WP-0.6-F05 (oracle_setup.sh directory robustness), and WP-0.6-F07 (default store path test). WP-0.6-F04 (target WP-0.7), WP-0.6-F06 (target WP-0.9), and WP-0.6-F08 (target WP-0.7) are accepted as debt in docs/progress/DEBT.md.
