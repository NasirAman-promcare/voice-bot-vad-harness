"""Gather every fact the merge-gate criteria need from git, files and GitHub.

CAPABILITIES:
  CAP-AUTONOMY-201: resolve the repository slug from remote.origin.url (HTTPS, SSH, proxy forms)
    [tests: test_FR_1_0_05_facts_slug_https, test_FR_1_0_05_facts_slug_ssh,
    test_FR_1_0_05_facts_slug_proxy_form]
  CAP-AUTONOMY-202: gather git facts: branch, head SHA, fetched origin/main SHA, merge base
    [tests: test_FR_1_0_05_facts_git_fields, test_FR_1_0_05_facts_missing_origin_main_raises,
    test_FR_1_0_05_facts_fetches_origin_once]
  CAP-AUTONOMY-203: read the audit report verdict, resolve the audited SHA and list later
    commits with their changed paths
    [tests: test_FR_1_0_05_facts_audit_fields, test_FR_1_0_05_facts_audit_missing_file,
    test_FR_1_0_05_facts_audit_bad_verdict, test_FR_1_0_05_facts_audit_abbreviated_sha,
    test_FR_1_0_05_facts_later_commits_paths]
  CAP-AUTONOMY-204: collect GitHub facts: open pull request, check runs, combined status
    [tests: test_FR_1_0_05_facts_github_fields, test_FR_1_0_05_facts_no_open_pr]
  CAP-AUTONOMY-205: collect findings, blockers, spec allowances, blocking checks and
    the status fragment
    [tests: test_FR_1_0_05_facts_open_blockers_for_wp, test_FR_1_0_05_facts_findings_rows,
    test_FR_1_0_05_facts_spec_from_origin_main, test_FR_1_0_05_facts_spec_missing,
    test_FR_1_0_05_facts_blocking_checks_and_reports, test_FR_1_0_05_facts_status_fragment]
  CAP-AUTONOMY-206: classify diff paths since the merge base against PROTECTED_PATHS.txt
    [tests: test_FR_1_0_05_facts_diff_paths_classified]
INPUTS AND OUTPUTS: gather(wp, repo_root, github) -> Facts (frozen dataclass); raises FactsError.
CONTRACTS: AUDIT_REPORT.md verdict format; FRAGMENTS.md; WP_SPEC.md; PROTECTED_PATHS.txt;
  tools.progress.fragments.load_all; tools.outsourcing.paths.classify.
INVARIANTS:
  - Gathering facts never writes to the repository and makes no commit.
  - The spec is read from origin/main with git show, never from the working tree.
  - GitHub access goes only through the injected github object.
  - Missing optional artefacts are represented as absent values, never fabricated.
NOT IN SCOPE:
  - Evaluating criteria (criteria.py), merging (merge_gate.py), calling gh directly (github.py).
CHANGE LOG:
  2026-10-10 WO-1.0-05 step 3 created."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from tools.outsourcing.paths import classify
from tools.progress.fragments import Fragments, load_all

__all__ = ["FactsError", "ChangedPath", "LaterCommit", "FindingRow", "BlockingCheck",
           "Facts", "gather", "slug_from_remote_url"]

_AUDIT_PATH = "docs/progress/{wp}/AUDIT.md"
_SPEC_GLOB = "docs/specs"
_STATUS_VALUES = {"NOT-STARTED", "PLANNED", "IN-BUILD", "READY-FOR-AUDIT", "AUDIT-FAIL",
                  "AUDIT-PASS", "MERGE-READY", "MERGED", "OWNER-RUN", "BLOCKED"}
_OPEN_FINDING_STATES = {"open", "accepted as debt"}
_SSH_PREFIXES = ("git@", "ssh://")
_HEX_RE = re.compile(r"^[0-9a-fA-F]{4,64}$")


class FactsError(Exception):
    """A fact needed by the gate could not be gathered; the message says what and why."""


class _GitHubLike(Protocol):
    def open_pr_for_branch(self, branch: str) -> dict[str, Any] | None: ...
    def check_runs(self, sha: str) -> list[dict[str, Any]]: ...
    def combined_status(self, sha: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ChangedPath:
    """One path changed in the diff since the merge base, with its protected class."""
    path: str
    protected_class: str


@dataclass(frozen=True)
class LaterCommit:
    """A commit between the audited SHA (exclusive) and head (inclusive)."""
    sha: str
    subject: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class FindingRow:
    """One CRITICAL or MAJOR row of the audit findings table."""
    finding_id: str
    severity: str
    state: str
    raw: str


@dataclass(frozen=True)
class BlockingCheck:
    """One spec owner-run check marked blocking, with its committed report state."""
    check_id: str
    passed: bool
    report_path: str | None


@dataclass(frozen=True)
class Facts:
    """Immutable bundle of every fact the seven criteria read."""
    wp: str
    repo_slug: str
    branch: str
    head_sha: str
    origin_main_sha: str
    merge_base: str
    branch_contains_origin_main: bool
    pull_request: dict[str, Any] | None
    check_runs: tuple[dict[str, Any], ...]
    combined_status: dict[str, Any]
    audit_exists: bool
    audit_verdict: str | None
    audited_sha: str | None
    audited_is_ancestor: bool
    later_commits: tuple[LaterCommit, ...]
    open_blockers: tuple[str, ...]
    critical_findings: tuple[FindingRow, ...]
    major_findings: tuple[FindingRow, ...]
    major_acceptances: tuple[str, ...]
    diff_paths: tuple[ChangedPath, ...]
    spec_exists: bool
    allowed_guarded_edits: tuple[str, ...]
    approvals_allow_edits: tuple[str, ...]
    blocking_checks: tuple[BlockingCheck, ...]
    status_state: str | None
    fragments: Fragments = field(compare=False)


def slug_from_remote_url(url: str) -> str:
    """Extract the owner/repo slug from an HTTPS, SSH or proxy remote URL."""
    text = url.strip()
    if text.endswith(".git"):
        text = text[:-4]
    for prefix in _SSH_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):]
            if ":" in text and "/" not in text.split(":", 1)[0]:
                text = text.split(":", 1)[1]
            else:
                parts = text.split("/")
                text = "/".join(parts[-2:])
            break
    else:
        parts = [part for part in text.split("/") if part]
        if len(parts) < 2:
            raise FactsError(f"cannot read a repository slug from remote URL {url!r}")
        text = "/".join(parts[-2:])
    parts = text.split("/")
    if len(parts) != 2 or not all(parts):
        raise FactsError(f"cannot read a repository slug from remote URL {url!r}")
    return text


def _git(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise FactsError(f"git {' '.join(args)} failed: {proc.stderr.strip() or 'no error text'}")
    return proc.stdout.strip()


def _git_lines(repo_root: Path, *args: str) -> list[str]:
    out = _git(repo_root, *args)
    return [line for line in out.splitlines() if line.strip()]


def _resolve_sha(repo_root: Path, ref: str) -> str | None:
    proc = subprocess.run(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], cwd=repo_root,
                          capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _read_audit(repo_root: Path, wp: str) -> tuple[bool, str | None, str | None, str]:
    path = repo_root / _AUDIT_PATH.format(wp=wp)
    if not path.is_file():
        return False, None, None, ""
    text = path.read_text(encoding="utf-8")
    verdict = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Verdict:"):
            verdict = stripped.split(":", 1)[1].strip()
            break
    audited: str | None = None
    marker = "Commit audited:"
    if marker in text:
        tail = text.split(marker, 1)[1]
        match = re.search(r"`([0-9a-fA-F]{4,64})`", tail)
        if match is not None:
            audited = match.group(1)
    return True, verdict, audited, text


def _later_commits(repo_root: Path, audited_sha: str, head_sha: str) -> tuple[LaterCommit, ...]:
    shas = _git_lines(repo_root, "rev-list", "--reverse", f"{audited_sha}..{head_sha}")
    commits: list[LaterCommit] = []
    for sha in shas:
        subject = _git(repo_root, "show", "-s", "--format=%s", sha)
        paths = tuple(sorted(_git_lines(repo_root, "diff-tree", "--no-commit-id", "--name-only", "-r", sha)))
        commits.append(LaterCommit(sha=sha, subject=subject, paths=paths))
    return tuple(commits)


def _is_ancestor(repo_root: Path, anc: str, desc: str) -> bool:
    proc = subprocess.run(["git", "merge-base", "--is-ancestor", anc, desc], cwd=repo_root,
                          capture_output=True, text=True, timeout=60)
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    raise FactsError(f"git merge-base --is-ancestor failed: {proc.stderr.strip()}")


def _finding_state(cells: list[str]) -> str:
    """Classify a findings-table row from its recommendation/state text."""
    joined = " ".join(cells).lower()
    if "accepted as debt" in joined:
        return "accepted as debt"
    if "fixed" in joined:
        return "fixed"
    return "open"


def _parse_findings(audit_text: str) -> tuple[tuple[FindingRow, ...], tuple[FindingRow, ...]]:
    critical: list[FindingRow] = []
    major: list[FindingRow] = []
    in_findings = False
    for line in audit_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_findings = stripped.lower().startswith("## findings")
            continue
        if not in_findings or not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 2 or cells[0] in ("ID", "---") or set(cells[0]) == {"-"}:
            continue
        severity = cells[1].upper()
        if severity not in ("CRITICAL", "MAJOR"):
            continue
        row = FindingRow(finding_id=cells[0], severity=severity, state=_finding_state(cells[2:]), raw=stripped)
        (critical if severity == "CRITICAL" else major).append(row)
    return tuple(critical), tuple(major)


def _major_acceptances(fragments: Fragments) -> tuple[str, ...]:
    accepted: list[str] = []
    for debt in sorted(fragments.debt, key=lambda d: str(d.path)):
        fields = {k.strip(): v.strip() for k, v in debt.fields.items()}
        if fields.get("Severity", "").upper() != "MAJOR":
            continue
        source = fields.get("Source", "")
        by = fields.get("Accepted by", "")
        if source and by:
            accepted.append(f"{source} <- {by}")
    for decision in sorted(fragments.decisions, key=lambda d: str(d.path)):
        text = "\n".join(f"{k}: {v}" for k, v in decision.fields.items())
        match = re.search(r"F-\d+\.\d+-\d+|F\d+|[A-Z]+-\d+\.\d+-\d+", text)
        if match is not None:
            accepted.append(match.group(0))
    return tuple(sorted(set(accepted)))


def _spec_text(repo_root: Path, wp: str) -> str | None:
    listing = _git_lines(repo_root, "ls-tree", "-r", "--name-only", "origin/main", "--", _SPEC_GLOB)
    candidates = sorted(p for p in listing if Path(p).name.startswith(f"{wp}-"))
    if not candidates:
        return None
    proc = subprocess.run(["git", "show", f"origin/main:{candidates[0]}"], cwd=repo_root,
                          capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise FactsError(f"git show origin/main:{candidates[0]} failed: {proc.stderr.strip()}")
    return proc.stdout


def _section_lines(spec: str, heading: str) -> list[str]:
    lines: list[str] = []
    in_section = False
    for line in spec.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped.lower().startswith(heading.lower())
            continue
        if in_section:
            lines.append(line)
    return lines


def _allowed_guarded_edits(spec: str) -> tuple[str, ...]:
    allowed: list[str] = []
    for line in _section_lines(spec, "## allowed guarded edits"):
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        value = stripped[1:].strip().strip("`").strip()
        if value and value.lower() != "none":
            allowed.append(value)
    return tuple(allowed)


def _approval_lines(repo_root: Path) -> tuple[str, ...]:
    listing = _git_lines(repo_root, "ls-tree", "-r", "--name-only", "origin/main", "--", "docs/approvals")
    lines: list[str] = []
    for path in sorted(listing):
        proc = subprocess.run(["git", "show", f"origin/main:{path}"], cwd=repo_root,
                              capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            continue
        for raw in proc.stdout.splitlines():
            stripped = raw.strip()
            if stripped.upper().startswith("ALLOW-EDIT:"):
                value = stripped.split(":", 1)[1].strip().strip("`").strip()
                if value:
                    lines.append(value)
    return tuple(sorted(set(lines)))


def _blocking_checks(spec: str, repo_root: Path, wp: str) -> tuple[BlockingCheck, ...]:
    checks: list[BlockingCheck] = []
    for line in _section_lines(spec, "## owner-run checks"):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 2 or cells[0] in ("Check", "---") or set(cells[0]) == {"-"}:
            continue
        if cells[1].strip().lower() != "blocking":
            continue
        first = cells[0].strip().strip("`")
        check_id = first.split()[0] if first.split() else ""
        if not check_id:
            raise FactsError(f"blocking owner-run check row has no check ID: {stripped!r}")
        checks.append(_report_state(repo_root, wp, check_id))
    return tuple(checks)


def _report_state(repo_root: Path, wp: str, check_id: str) -> BlockingCheck:
    folder = repo_root / "docs" / "progress" / wp
    reports: list[Path] = []
    if folder.is_dir():
        reports = sorted(p for p in folder.iterdir() if p.is_file() and p.name.startswith(check_id))
    for report in reports:
        for raw in report.read_text(encoding="utf-8").splitlines():
            if raw.strip() == "Result: PASS":
                rel = report.relative_to(repo_root).as_posix()
                return BlockingCheck(check_id=check_id, passed=True, report_path=rel)
    rel = reports[0].relative_to(repo_root).as_posix() if reports else None
    return BlockingCheck(check_id=check_id, passed=False, report_path=rel)


def _status_state(fragments: Fragments, wp: str) -> str | None:
    for fragment in fragments.status:
        fields = {k.strip(): v.strip() for k, v in fragment.fields.items()}
        if fields.get("WP") == wp:
            state = fields.get("Status", "").strip()
            if state and state not in _STATUS_VALUES:
                raise FactsError(f"status fragment for {wp} has unknown Status {state!r}")
            return state or None
    return None


def _open_blockers(fragments: Fragments, wp: str) -> tuple[str, ...]:
    open_ids: list[str] = []
    for blocker in sorted(fragments.blockers, key=lambda b: str(b.path)):
        fields = {k.strip(): v.strip() for k, v in blocker.fields.items()}
        if fields.get("WP") == wp and fields.get("Status", "").upper() == "OPEN":
            open_ids.append(Path(blocker.path).stem)
    return tuple(open_ids)


def _diff_paths(repo_root: Path, merge_base: str, head_sha: str) -> tuple[ChangedPath, ...]:
    paths = sorted(set(_git_lines(repo_root, "diff", "--name-only", merge_base, head_sha)))
    return tuple(ChangedPath(path=p, protected_class=classify(p, repo_root)) for p in paths)


def gather(wp: str, repo_root: Path, github: _GitHubLike) -> Facts:
    """Collect every fact the merge-gate criteria need, without writing anything."""
    root = Path(repo_root)
    top = _git(root, "rev-parse", "--show-toplevel")
    if Path(top).resolve() != root.resolve():
        root = Path(top)
    url = _git(root, "config", "--get", "remote.origin.url")
    slug = slug_from_remote_url(url)
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    head_sha = _git(root, "rev-parse", "HEAD")
    _git(root, "fetch", "origin", "main")
    origin_main_sha = _resolve_sha(root, "origin/main")
    if origin_main_sha is None:
        raise FactsError("origin/main is missing after git fetch origin main; cannot check the base")
    merge_base = _git(root, "merge-base", "origin/main", head_sha)
    contains = _is_ancestor(root, origin_main_sha, head_sha)

    pull_request = github.open_pr_for_branch(branch)
    check_runs = tuple(github.check_runs(head_sha))
    combined_status = github.combined_status(head_sha)

    audit_exists, verdict, audited_raw, audit_text = _read_audit(root, wp)
    audited_sha: str | None = None
    audited_is_ancestor = False
    later: tuple[LaterCommit, ...] = ()
    if audited_raw is not None:
        audited_sha = _resolve_sha(root, audited_raw)
        if audited_sha is None:
            raise FactsError(f"audited commit {audited_raw!r} in {_AUDIT_PATH.format(wp=wp)} "
                             "does not resolve to a commit")
        audited_is_ancestor = _is_ancestor(root, audited_sha, head_sha)
        if audited_is_ancestor:
            later = _later_commits(root, audited_sha, head_sha)

    fragments = load_all(root)
    critical, major = _parse_findings(audit_text) if audit_exists else ((), ())
    spec = _spec_text(root, wp)
    spec_exists = spec is not None
    allowed = _allowed_guarded_edits(spec) if spec_exists else ()
    approvals = _approval_lines(root)
    blocking = _blocking_checks(spec, root, wp) if spec_exists else ()

    return Facts(
        wp=wp, repo_slug=slug, branch=branch, head_sha=head_sha,
        origin_main_sha=origin_main_sha, merge_base=merge_base, branch_contains_origin_main=contains,
        pull_request=pull_request, check_runs=check_runs, combined_status=combined_status,
        audit_exists=audit_exists, audit_verdict=verdict, audited_sha=audited_sha,
        audited_is_ancestor=audited_is_ancestor, later_commits=later,
        open_blockers=_open_blockers(fragments, wp),
        critical_findings=critical, major_findings=major,
        major_acceptances=_major_acceptances(fragments),
        diff_paths=_diff_paths(root, merge_base, head_sha),
        spec_exists=spec_exists, allowed_guarded_edits=allowed, approvals_allow_edits=approvals,
        blocking_checks=blocking, status_state=_status_state(fragments, wp),
        fragments=fragments,
    )
