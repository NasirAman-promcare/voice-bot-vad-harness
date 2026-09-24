# Testing and evidence

- **Test first.** For each requirement ID write a test named after it, such as `test_FR_0_2_03_rejects_missing_clip_id`. Run it, see it fail for the right reason, then implement.
- **Markers**: `slow`, `gpu`, `colab`, `oracle`, `network`. The fast suite excludes them all.
- **Real code paths.** Test doubles are allowed only for external services the spec says cannot run here (GPU, Google Drive, Jitsi, Oracle cores), and only inside `tests/`. Production code never checks whether it is under test.
- **Meaningful assertions.** Each test must fail if the behaviour it names were removed or broken. Prefer expected values computed independently in the test from the spec's definition.
- **Evidence.** In `docs/progress/<WP>/EVIDENCE.md`, list each requirement ID with its tests, the exact command, and a real output excerpt. Never paraphrase output you did not see.
- **Before "ready for audit"**: run the fast suite, the audit gate and every acceptance command in the spec, and paste the real results into `EVIDENCE.md`.
