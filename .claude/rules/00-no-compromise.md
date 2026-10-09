# No-compromise rules

These count as compromise. Never introduce them in `aqis_lab/`, `tools/` or `kit-staging/` unless the WP spec explicitly requires it:
- **Stubs and placeholders**: `pass`-only bodies, `NotImplementedError` outside an abstract base class, `TODO`, `FIXME`, `XXX`, "placeholder", "simplified", "for now", "temporary", "hack", "dummy", "fake".
- **Fake data**: invented numbers or transcripts, synthetic results presented as measured, defaults that hide a missing input. **A missing real input means stop, never a stand-in**: generated beeps in place of recordings, made-up probe values, or a downloaded substitute dataset nobody approved.
- **Silent failure**: `except: pass`, broad excepts that swallow errors, returning empty results on error without raising or emitting a structured error event.
- **Test gaming**: skip or xfail added to get green, loosened assertions, expected values copied from current output without independent justification, code that behaves differently under test.
- **Scope drift**: features not in the spec, "while I'm here" refactors, renamed public functions, reformatting untouched code.

If a flagged pattern is genuinely required, such as an abstract method, add `# audit-allow: <reason>` on that line. The audit lists every such line.

"Smallest code" never means less: validation at trust boundaries, error handling, logging contracts, requirement coverage and tests are never cut to save lines or tokens.

When you cannot meet a requirement fully, follow `.claude/rules/10-autonomy-and-escalation.md`. A partial result is acceptable only when labelled `PARTIAL` in `EVIDENCE.md` and in your message, and the WP stays open.
