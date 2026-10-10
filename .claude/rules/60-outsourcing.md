---
paths:
  - "docs/outsourcing/**"
  - "tools/outsourcing/**"
---

# Outsourcing work orders

- Every work order follows `docs/process/outsourcing/templates/WORK_ORDER.md` exactly, including the machine-readable front matter and, above 3 outputs, a step plan by its sizing rules. The relay rejects anything else.
- Write the must-catch acceptance tests and commit them before the order is sent. List them under `read_only_tests`; the implementer never sees permission to change them.
- `outputs` lists every file the implementer may create or replace. Nothing under NEVER or GUARDED paths, nothing under `tests/aqis_lab/breaks/`, and no read-only test may appear there.
- `context` lists only what the implementer must read in full; modules it only calls go under `interfaces`. Never secrets, `.env` files, keys, tokens, personal data or client data.
- Describe interfaces in words and tables, not code. If you find yourself writing the implementation in the order, it belongs in Claude, not in a work order.
- Reach model APIs only through the relay, never with curl, a script of your own, or another key, account or project. The relay picks models from `config/aqis_lab/model_pool.json` and paces itself under their limits; its exit code says when to run it again.
- After the relay returns: read its report and summary only, then audit the files with `docs/process/outsourcing/templates/WO_REVIEW_CHECKLIST.md`. Small gaps under about 30 lines you fix yourself; anything larger becomes a fix order or a clarified work order.
- QUESTIONS returned by the implementer are answered by amending the work order, never by guessing in your own code.
