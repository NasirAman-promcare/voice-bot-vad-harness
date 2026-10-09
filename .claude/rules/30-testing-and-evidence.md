# Testing and evidence

- **Test first.** For each requirement ID write a test named after it, such as `test_FR_1_2_03_rejects_clipped_input`. See it fail for the right reason, then implement.
- **Acceptance tests are the trust anchor.** Must-catch acceptance tests are written by you before any implementation, including outsourced implementation, and the implementer never edits them.
- **Break recipes.** For each must-catch behaviour, add a break recipe under `tests/aqis_lab/breaks/<WP>/` (format `docs/process/templates/BREAK_RECIPE.md`). The break suite applies each one and confirms the named tests fail.
- **Markers**: `slow`, `gpu`, `colab`, `oracle`, `network`. The fast suite excludes them all.
- **Real code paths.** Test doubles only for external services that cannot run here (GPU, Drive, Jitsi, GitHub API, Gemini API, Oracle cores), only inside `tests/`. Production code never checks whether it is under test.
- **Meaningful assertions.** Each test fails if its behaviour is removed or broken. Prefer expected values computed independently from the spec's definition.
- **Run little, often; run all, rarely.** While building, run the tests your change affects (impact tool, or the module's tests). Run the full fast suite before READY-FOR-AUDIT; CI runs everything else.
- **Quiet output.** `pytest -q --tb=short`; send long output to a file under `/tmp` and read it with `grep` or `tail`, or hand it to `log-digest`.
- **Evidence.** In `docs/progress/<WP>/EVIDENCE.md`, list each requirement ID with its tests, the exact command and a real output excerpt. Never paraphrase output you did not see.
