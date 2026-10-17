#!/usr/bin/env python3
"""SessionStart hook: print a short orientation. Claude Code adds this stdout to Claude's context.

Results-first version (17 Oct 2026): branch, the current sprint brief and where the rules are.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never leave cache files inside .claude/
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protected import project_root  # noqa: E402

BRIEF_RE = re.compile(r"^WP-(\d+)\.(\d+)-.+\.md$")


def current_brief(root):
    """The sprint brief with the highest WP number under docs/specs/sprints/, or None."""
    folder = root / "docs" / "specs" / "sprints"
    if not folder.is_dir():
        return None
    briefs = []
    for path in folder.iterdir():
        m = BRIEF_RE.match(path.name)
        if m and path.is_file():
            briefs.append(((int(m.group(1)), int(m.group(2))), path))
    return max(briefs)[1] if briefs else None


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
    note = "  <- this is main: create a branch before you commit" if branch in ("main", "master") else ""
    brief = current_brief(root)
    out = [
        "AQIS LAB SESSION CONTEXT (results-first; printed by .claude/hooks/session_context.py)",
        f"- Branch: {branch}{note}",
        f"- Current sprint brief: {brief.relative_to(root).as_posix() if brief else 'none under docs/specs/sprints/'}",
        "- Rules: CLAUDE.md (one page). Hooks guard owner-only paths; the stop gate scans new lab lines "
        "and runs the fast tests.",
    ]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
