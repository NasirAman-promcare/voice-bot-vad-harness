---
paths:
  - "kit-staging/**"
  - "tests/aqis_lab/kit/**"
---

# Kit staging

`kit-staging/` mirrors `.claude/` for hook and settings code that is written and audited here, then installed by the owner (KIT capability). It is enforcement code, so it is always audited at tier T1.

- Hooks use the standard library only, set `sys.dont_write_bytecode = True`, and follow the current Claude Code hooks reference for input and output.
- Enforcement hooks fail closed: on bad input or an internal error they block and explain. Advisory hooks (the loop guard) fail open and log to `.git/aqis-*.log`.
- Hooks never call the network and never modify the working tree except their own state files under `.git/`.
- Tests for staged hooks live in `tests/aqis_lab/kit/` and run the hook as a subprocess with real JSON input, exactly as Claude Code would.
- After installation, `.claude/` must be byte-identical to `kit-staging/` for every staged file; the kit parity check enforces this.
