# Approvals (owner only)

Only you, the owner, create files here, and only on `main`, using the GitHub website. Claude cannot edit this folder, and the hooks read approvals from `origin/main`, so an approval made anywhere else has no effect.

- Approve a plan: create `WP-x.y.md` from `docs/process/templates/APPROVAL.md`.
- Unlock one protected harness file or an existing test: add a line `ALLOW-EDIT: <path>`.
- Let a file legitimately contain forbidden words (for example the pattern list itself): add `ALLOW-PATTERNS-IN: <path>`.
- Make an approval temporary: add `EXPIRES: YYYY-MM-DD`.
- Withdraw an approval: change `STATUS: APPROVED` to `STATUS: WITHDRAWN`.

Full rules: `docs/process/CHANGE_CONTROL.md`.
