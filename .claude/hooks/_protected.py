"""Shared helpers for the AQIS lab Claude Code hooks. Standard library only.

Reads docs/process/PROTECTED_PATHS.txt and docs/approvals/*.md (both owner-owned).
"""
import os
import re
import subprocess
from datetime import date
from pathlib import Path

SECTIONS = ("NEVER", "GUARDED", "LAB-OWNED")
# Always enforced, even if the list file is missing or damaged.
DEFAULT_NEVER = ("CLAUDE.md", ".claude/**", "docs/specs/**", "docs/process/**", "docs/approvals/**")


def project_root(event=None):
    """Repository root: CLAUDE_PROJECT_DIR, else the event's cwd, else the process cwd."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    if event and event.get("cwd"):
        return Path(event["cwd"]).resolve()
    return Path.cwd().resolve()


def glob_to_regex(pattern):
    """Convert a repo-relative glob with **, * and ? into an anchored regular expression."""
    pattern = pattern.strip().lstrip("/")
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            if pattern[i:i + 3] == "**/":
                out.append("(?:.*/)?")
                i += 3
                continue
            if pattern[i:i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def load_patterns(root):
    """Return {section: [compiled regex, ...]} from PROTECTED_PATHS.txt plus the built-in NEVER list."""
    sections = {name: [] for name in SECTIONS}
    current = None
    try:
        text = (Path(root) / "docs" / "process" / "PROTECTED_PATHS.txt").read_text(encoding="utf-8")
    except OSError:
        text = ""
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        header = re.fullmatch(r"\[([A-Z-]+)\]", line)
        if header:
            current = header.group(1) if header.group(1) in SECTIONS else None
            continue
        if current:
            sections[current].append(glob_to_regex(line))
    sections["NEVER"].extend(glob_to_regex(p) for p in DEFAULT_NEVER)
    return sections


def classify(rel, sections):
    """Return 'NEVER', 'LAB', 'GUARDED' or None for a repo-relative POSIX path."""
    rel = rel.replace(os.sep, "/")
    if any(rx.match(rel) for rx in sections["NEVER"]):
        return "NEVER"
    if any(rx.match(rel) for rx in sections["LAB-OWNED"]):
        return "LAB"
    if any(rx.match(rel) for rx in sections["GUARDED"]):
        return "GUARDED"
    return None


def relpath_in_project(root, path, cwd=None):
    """Repo-relative POSIX path for a tool target, or None when it lies outside the repository."""
    root = Path(root)
    p = Path(path)
    if not p.is_absolute():
        p = Path(cwd or root) / p
    p = Path(os.path.normpath(str(p)))
    for candidate in (p, p.resolve() if p.exists() else p):
        try:
            return candidate.relative_to(root).as_posix()
        except ValueError:
            continue
    return None


def _git(root, *args):
    try:
        proc = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30)
        return proc.returncode, proc.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def main_ref(root):
    """Best reference for owner-approved state: origin/main (fetched if missing), else main, else None."""
    for attempt in range(2):
        for ref in ("origin/main", "main"):
            if _git(root, "rev-parse", "--verify", "--quiet", ref)[0] == 0:
                return ref
        if attempt == 0:
            _git(root, "fetch", "--quiet", "origin", "main:refs/remotes/origin/main")
    return None


def approval_texts(root, ref):
    """[(file name, text)] of approval files as committed at ref.

    Without a verified main reference no approval counts (fail closed): approvals are never read
    from the working tree, where a branch could have forged them.
    """
    root = Path(root)
    if not ref:
        return []
    if ref:
        rc, out = _git(root, "ls-tree", "--name-only", f"{ref}:docs/approvals")
        names = [n for n in out.splitlines() if n.endswith(".md")] if rc == 0 else []
        texts = []
        for name in names:
            rc2, text = _git(root, "show", f"{ref}:docs/approvals/{name}")
            if rc2 == 0:
                texts.append((name, text))
        return texts
    return []


def load_approvals(root, ref=None):
    """Return (edit_rules, pattern_rules, files) from approval files with STATUS: APPROVED at ref.

    Pass ref (for example origin/main or the merge-base) so that only owner-committed approvals count.
    Each rule is (compiled regex, approval file name, original glob).
    ALLOW-EDIT unlocks GUARDED paths and existing lab tests.
    ALLOW-PATTERNS-IN exempts files from the compromise-pattern scan (for example, pattern definitions).
    An EXPIRES: YYYY-MM-DD line ends the approval after that date.
    """
    edit_rules, pattern_rules, files = [], [], []
    today = date.today().isoformat()
    for name, text in approval_texts(root, ref):
        if name.lower() == "readme.md":
            continue
        if not re.search(r"^STATUS:\s*APPROVED\s*$", text, re.M):
            continue
        expires = re.search(r"^EXPIRES:\s*(\d{4}-\d{2}-\d{2})\s*$", text, re.M)
        if expires and expires.group(1) < today:
            continue
        files.append(name)
        for m in re.finditer(r"^ALLOW-EDIT:\s*(\S+)\s*$", text, re.M):
            edit_rules.append((glob_to_regex(m.group(1)), name, m.group(1)))
        for m in re.finditer(r"^ALLOW-PATTERNS-IN:\s*(\S+)\s*$", text, re.M):
            pattern_rules.append((glob_to_regex(m.group(1)), name, m.group(1)))
    return edit_rules, pattern_rules, files
