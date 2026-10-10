# Work order template

Copy everything below the line into `docs/outsourcing/orders/<WO-ID>.md`. The front matter uses a strict subset of YAML that the relay parses without a YAML library: top-level `key: value` lines; lists as lines of two spaces, a dash and a space; a `#` after a space starts a comment. Nothing else.

## Sizing the steps
Gemini writes an order one step at a time, because small requests get better answers and fit the free tier's per-minute token limit.
- One step is one module and its test file, plus `__init__.py` files or a tiny file: at most 3 paths, not counting `__init__.py`.
- Order the steps so that each step calls only what earlier steps or `interfaces` provide: leaf modules first, the command line last.
- At most about 400 output lines per step (files of at most 300 lines each). A bigger module is split into modules, not into steps.
- Keep each step's request under about 30,000 input tokens: list modules the implementer only calls under `interfaces`, not `context`. `relay --dry-run` shows the figure per step.
- Aim for 3 to 6 steps. An order that needs more than 8 should be two orders; the parser refuses more than 10.
- When another order's tests share the folder, `verify` names this order's own test files.

---

```text
---
id: WO-<x.y>-<nn>
wp: WP-<x.y>
title: <short title>
model: default                     # default = the router picks from config/aqis_lab/model_pool.json; or pin one model listed there
channel: api                       # api | jules | paste
attempt_budget: 3                  # 1 to 5, per step and for the final verification
risk_tier: T2                      # T1 | T2 | T3 (decides which pool models may write it)
max_output_tokens: 40000           # per answer: one step's files plus the DOD table
context:                           # sent in full, in this order (the Foundation and the return format are added automatically)
  - docs/process/CHANGE_CONTROL.md
  - <contracts, and files the implementer must read in full or change>
interfaces:                        # optional: modules the implementer only calls, sent as interface views
  - <path>.py
outputs:                           # the only paths the implementer may create or replace
  - <path>
steps:                             # required when outputs has more than 3 paths, not counting __init__.py
  - <module>.py, tests/aqis_lab/<package>/test_<module>.py
read_only_tests:                   # acceptance tests Claude wrote; must pass unmodified
  - <path>
allowed_dependencies:              # "stdlib" or packages already pinned in requirements/aqis_lab
  - stdlib
verify:                            # commands the relay runs, in order, after the last step
  - .venv/bin/python -m pytest <paths> -q --tb=short
---
```

# <WO-ID> — <title>

## 1. Context
<Two to five sentences: where this fits in the WP and the lab, what already exists, and which contract or modules it meets. Name the files in `context` and `interfaces` and say what to take from each.>

## 2. Your job
<One paragraph in behaviour terms: what the files do, for whom, with which inputs and outputs.>

## 3. Files you create
| Path | One responsibility | Public API (names, inputs, outputs, errors, in words) | Max lines |
| --- | --- | --- | --- |

## 4. Required behaviour
- **B1** (<spec IDs>) <testable statement>
- **B2** ...

## 5. Edge cases you must handle
- **E1** <input or situation> → <required result>

## 6. Never
- Never create or edit any path not in `outputs`, and never touch `read_only_tests`.
- Never add a dependency outside `allowed_dependencies`.
- <work-order-specific prohibitions>

## 7. When this order is wrong or incomplete
Return a QUESTIONS block (see `RETURN_FORMAT.md`) and no files. In particular, ask when: <the known open points, if any>.

## 8. Must-catch behaviours (what the acceptance tests and break recipes protect)
1. <behaviour>

## 9. Definition of Done
- **D1** Every file in section 3 exists with the stated public API and the module header standard.
- **D2** Every behaviour B1 to Bn and edge case E1 to En is implemented; point at each.
- **D3** Unit tests for your own logic exist where section 3 says, and pass.
- **D4** The read-only acceptance tests pass unmodified.
- **D5** Nothing in the Never list is violated; no placeholder, swallowed error or fabricated value exists.
- **D6** <work-order-specific items>

## 10. Channel notes
- **api / paste**: answer in `RETURN_FORMAT.md` form, one step at a time, as the step block of each request says.
- **jules**: first read `docs/process/outsourcing/FOUNDATION.md`, `docs/process/outsourcing/templates/RETURN_FORMAT.md`, every file in `context` and every file in `interfaces`; then write the files directly at the listed paths on branch `wo/<WO-ID>`, one step at a time in the order of `steps`, run every `verify` command until it passes, and open a pull request titled `<WO-ID>: <title>` whose description is the DOD table.
