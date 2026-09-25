#!/usr/bin/env python3
"""SessionStart hook: print a short orientation. Claude Code adds this stdout to Claude's context."""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never leave cache files inside .claude/
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protected import project_root  # noqa: E402

ROW_RE = re.compile(r"^\|\s*(WP-[\d.]+)\s*\|[^|]*\|\s*([A-Z-]+)\s*\|", re.M)


def main():
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        event = {}
    root = project_root(event)
    try:
        branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root,
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=20).stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        branch = "unknown"
    out = ["AQIS LAB SESSION CONTEXT (printed by .claude/hooks/session_context.py)"]
    note = "  <- this is main: do not commit here" if branch in ("main", "master") else ""
    out.append(f"- Branch: {branch}{note}")
    status_file = root / "docs" / "progress" / "STATUS.md"
    if status_file.is_file():
        rows = ROW_RE.findall(status_file.read_text(encoding="utf-8", errors="replace"))
        if rows:
            out.append("- WP status: " + ", ".join(f"{wp}={state}" for wp, state in rows))
    blockers_file = root / "docs" / "progress" / "BLOCKERS.md"
    if blockers_file.is_file():
        text = blockers_file.read_text(encoding="utf-8", errors="replace")
        open_ids = []
        for block in re.split(r"^(?=## BLK-)", text, flags=re.M):
            head = re.match(r"## (BLK-\S+)", block)
            if head and re.search(r"^STATUS:\s*OPEN\s*$", block, re.M):
                open_ids.append(head.group(1))
        out.append(f"- Open blockers: {', '.join(open_ids) if open_ids else 'none'}")
    for probe in ("colab_probe.txt", "oracle_probe.txt"):
        present = (root / "docs" / "environment" / probe).is_file()
        out.append(f"- docs/environment/{probe}: {'present' if present else 'MISSING (stop and ask if a task needs it)'}")
    out.append("- Rules: build fully to spec; stop and ask when blocked (ask-owner skill); change only the "
               "approved change budget; tests first; evidence for every claim; same results on cloud VM, "
               "Colab and Oracle. Protected paths and a stop gate are enforced by hooks.")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
