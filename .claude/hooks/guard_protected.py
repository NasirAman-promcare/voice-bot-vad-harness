#!/usr/bin/env python3
"""PreToolUse hook for Edit, Write and NotebookEdit: block edits to protected paths.

Exit code 2 blocks the tool call and shows the stderr message to Claude.
Protected paths come from docs/process/PROTECTED_PATHS.txt; approvals from docs/approvals/.
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never leave cache files inside .claude/
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protected import (classify, load_approvals, load_patterns, main_ref,  # noqa: E402
                        project_root, relpath_in_project)


def main():
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        print("BLOCKED: guard_protected could not read the hook input, so it blocks to stay safe. "
              "Tell the owner (ask-owner skill) if this repeats.", file=sys.stderr)
        return 2
    tool_input = event.get("tool_input") or {}
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not target:
        return 0
    root = project_root(event)
    rel = relpath_in_project(root, target, event.get("cwd"))
    if rel is None:
        return 0  # outside the repository, for example /tmp scratch space
    kind = classify(rel, load_patterns(root))
    if kind == "NEVER":
        print(f"BLOCKED: '{rel}' is owner-only (NEVER list in docs/process/PROTECTED_PATHS.txt). "
              "Do not try any other way to change it: no Bash, scripts, copies or renames. "
              "If it must change, use the ask-owner skill and describe the exact edit for the owner.",
              file=sys.stderr)
        return 2
    if kind == "GUARDED":
        edit_rules, _, _ = load_approvals(root, main_ref(root))
        if any(rx.match(rel) for rx, _, _ in edit_rules):
            return 0
        print(f"BLOCKED: '{rel}' is protected existing harness code (GUARDED list in "
              "docs/process/PROTECTED_PATHS.txt). Do not work around this. If the change is truly "
              "required, use the ask-owner skill; the owner can allow it by committing an approval "
              f"file to main with the line 'ALLOW-EDIT: {rel}'.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
