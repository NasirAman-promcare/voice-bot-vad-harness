# BLK-1.0-05 — The generated registry cannot hold the 40 capabilities that no Python header lists
Status: OPEN
WP: WP-1.0
Owner capability: DECISION
Raised: 2026-10-10
Session: https://claude.ai/code/session_01MdrFmVCBzGrRzg4n2dVGRx
Unblocks: WP-1.0 (FR-1.0-03, WO-1.0-03; then WO-1.0-06, WO-1.0-07 and WO-1.0-09, which use tools/index)
Time needed: 5 minutes
Loop: none

What I need: a choice of where the registry's non-Python capabilities live, and, for option 1, one added line in the WP-1.0 spec's Touches.

Why: FR-1.0-03 says the registry is generated from module headers, and that `--adopt-registry` accounts for every legacy row. WO-1.0-03 B7 says adoption refuses, writing nothing, when a row is "absent from headers and not retired". Of the 152 rows in `docs/capabilities/REGISTRY.md`:
- 112 are Python modules whose header names the capability;
- 39 are active capabilities of non-Python artifacts: 22 `.md` documents, 3 `.sh` scripts, locks (`.txt`), workflows (`.yml`), configs (`.yaml`, `.json`), 1 `.csv` and 1 `.ipynb`;
- 1 is `CAP-TEST-001` (`tests/aqis_lab/conftest.py`), whose docstring does not name it.

So adoption as written can never succeed. On `main`, the first generation would also drop those 40 rows and raise `CapabilityRemoved`. Retiring them would be false: they are working capabilities with tests.

What I tried:
- Counted the rows with a script over `REGISTRY.md`: 113 rows have `.py` modules; 112 of them are named in their module's docstring; the other 39 rows are non-Python.
- Checked the spec's Touches: it names `docs/capabilities/retired.d/**` only, so a new folder for these rows needs the spec.

Options:
1. **Capability records** (recommended).
   - **What.** One file per non-code capability, `docs/capabilities/records.d/<CAP-ID>.md`, holding the row's cells verbatim. `--adopt-registry` creates them for every legacy row whose capability no Python header names, then lists each created record.
   - **Generation.** The generator merges headers, records and retirements into `REGISTRY.md`, with the same seven columns the audit gate checks today.
   - **Later WPs.** A WP that adds a non-code capability adds a record. A record can disappear only with a retirement, exactly like a header capability.
   - **Cost.** One added Touches line: `docs/capabilities/records.d/**`.
   - **Conftest row.** `CAP-TEST-001` becomes a record too, so `tests/aqis_lab/conftest.py` stays untouched.
2. **Comment headers.** Extend the scanner to read capability headers from comments in `.sh`, `.yml`, `.yaml` and `.txt` files, and use records only for `.md`, `.json`, `.csv` and `.ipynb`. More code, two mechanisms, and every such file gets edited to add a header.
3. **Hand-written section.** Keep a hand-written section below the generated table for non-code rows. This contradicts "generated, never edited by hand", and nothing would stop a row from vanishing.

Exact steps:
1. Reply with "option 1", "option 2" or "option 3". For option 1, go on with steps 2 to 4.
2. On GitHub, branch `main`, open `docs/specs/phase-1/WP-1.0-operating-model-v2.md` and choose Edit.
3. In the **Touches** line, after `` `docs/capabilities/retired.d/**`, `` add `` `docs/capabilities/records.d/**`, `` and commit to `main`.
4. Tell this session "BLK-1.0-05 answered".

Meanwhile: WO-1.0-04 runs through the relay. I write the acceptance tests for WO-1.0-03 (Map, symbols, callers, test map, impact and the registry, the registry part written for option 1 and adjusted if you choose otherwise), and for WO-1.0-05 and WO-1.0-08. WO-1.0-03 is sent once you answer.

Owner answer:
