# Work order template

Copy everything below the line into `docs/outsourcing/orders/<WO-ID>.md`. The front matter uses a strict subset of YAML that the relay parses without a YAML library: top-level `key: value` lines; lists as lines of two spaces, a dash and a space; a `#` after a space starts a comment. Nothing else.

---

```text
---
id: WO-<x.y>-<nn>
wp: WP-<x.y>
title: <short title>
model: gemini-3.7-flash
channel: api                       # api | jules | paste
attempt_budget: 3                  # 1 to 5
risk_tier: T2                      # T1 | T2 | T3
max_output_tokens: 60000
context:                           # sent read-only, in this order (the Foundation and the return format are added automatically)
  - docs/process/CHANGE_CONTROL.md
  - <contracts and the exact modules to call>
outputs:                           # the only paths the implementer may create or replace
  - <path>
read_only_tests:                   # acceptance tests Claude wrote; must pass unmodified
  - <path>
allowed_dependencies:              # "stdlib" or packages already pinned in requirements/aqis_lab
  - stdlib
verify:                            # commands the relay runs, in order, after import
  - .venv/bin/python -m pytest <paths> -q --tb=short
---
```

# <WO-ID> — <title>

## 1. Context
<Two to five sentences: where this fits in the WP and the lab, what already exists, and which contract or modules it meets. Name the files in `context` and say what to take from each.>

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
- **api / paste**: answer in `RETURN_FORMAT.md` form.
- **jules**: first read `docs/process/outsourcing/FOUNDATION.md`, `docs/process/outsourcing/templates/RETURN_FORMAT.md` and every file in `context`; then write the files directly at the listed paths on branch `wo/<WO-ID>`, run every `verify` command until it passes, and open a pull request titled `<WO-ID>: <title>` whose description is the DOD table.
