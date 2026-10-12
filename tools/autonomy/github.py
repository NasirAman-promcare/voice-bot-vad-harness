"""GitHub REST client over the gh command, with pagination and error handling.

CAPABILITIES:
  CAP-AUTONOMY-101: look up the open pull request for a branch
    [tests: test_FR_1_0_05_gh_open_pr_for_branch, test_FR_1_0_05_gh_open_pr_none]
  CAP-AUTONOMY-102: fetch check runs for a commit, paginating until a short page
    [tests: test_FR_1_0_05_gh_check_runs_single_page, test_FR_1_0_05_gh_check_runs_paginates]
  CAP-AUTONOMY-103: fetch the combined status for a commit
    [tests: test_FR_1_0_05_gh_combined_status]
  CAP-AUTONOMY-104: merge a pull request pinned to a head SHA and confirm the response
    [tests: test_FR_1_0_05_gh_merge_pr_success, test_FR_1_0_05_gh_merge_pr_refused]
  CAP-AUTONOMY-105: raise GitHubError carrying the HTTP status on gh failure
    [tests: test_FR_1_0_05_gh_error_carries_status]
INPUTS AND OUTPUTS: GitHub(repo_slug) with methods open_pr_for_branch(branch), check_runs(sha),
  combined_status(sha), merge_pr(number, sha, title); raises GitHubError with a .status attribute.
CONTRACTS: gh CLI REST subset; REST responses as parsed JSON.
INVARIANTS:
  - Only `gh api` is invoked; never `gh pr merge` or GraphQL.
  - Check runs are paged with per_page=100 until a short page.
  - The merge call pins the head SHA and uses merge_method=merge.
NOT IN SCOPE:
  - Authentication setup (gh is pre-authenticated), caching, rate limiting.
CHANGE LOG:
  2026-10-10 WO-1.0-05 step 2 created.
  2026-10-10 WO-1.0-05 fix 2: _error_from_stderr missed trailing colon on the
    status token ("409:"); strip punctuation before the digit test.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any

__all__ = ["GitHubError", "GitHub"]

_PER_PAGE = 100


class GitHubError(Exception):
    """A gh api call failed; .status holds the HTTP status code when known."""

    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class GitHub:
    """Minimal GitHub REST client that shells out to `gh api`."""

    repo_slug: str

    def _api(self, endpoint: str, method: str = "GET",
             fields: tuple[tuple[str, str], ...] = ()) -> Any:
        """Run `gh api` and return parsed JSON; raise GitHubError on failure."""
        cmd = ["gh", "api"]
        if method != "GET":
            cmd.extend(["--method", method])
        cmd.append(endpoint)
        for key, value in fields:
            cmd.extend(["-f", f"{key}={value}"])
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            raise _error_from_stderr(proc.stderr)
        if not proc.stdout.strip():
            return None
        return json.loads(proc.stdout)

    def open_pr_for_branch(self, branch: str) -> dict[str, Any] | None:
        """Return the open pull request whose head is this branch, or None."""
        owner = self.repo_slug.split("/")[0]
        endpoint = f"repos/{self.repo_slug}/pulls?head={owner}:{branch}&state=open"
        data = self._api(endpoint)
        if not data:
            return None
        return data[0]

    def check_runs(self, sha: str) -> list[dict[str, Any]]:
        """Return every check run for a commit, paginating until a short page."""
        all_runs: list[dict[str, Any]] = []
        page = 1
        while True:
            endpoint = (f"repos/{self.repo_slug}/commits/{sha}/check-runs"
                        f"?per_page={_PER_PAGE}&page={page}")
            data = self._api(endpoint)
            runs = data.get("check_runs", [])
            all_runs.extend(runs)
            if len(runs) < _PER_PAGE:
                break
            page += 1
        return all_runs

    def combined_status(self, sha: str) -> dict[str, Any]:
        """Return the combined status for a commit."""
        return self._api(f"repos/{self.repo_slug}/commits/{sha}/status")

    def merge_pr(self, number: int, sha: str, title: str) -> dict[str, Any]:
        """Merge a pull request pinned to a head SHA; raise if not merged."""
        endpoint = f"repos/{self.repo_slug}/pulls/{number}/merge"
        data = self._api(endpoint, method="PUT", fields=(
            ("merge_method", "merge"),
            ("sha", sha),
            ("commit_title", title),
        ))
        if not isinstance(data, dict) or not data.get("merged"):
            raise GitHubError(f"GitHub refused the merge: {data}", status=0)
        return data


def _error_from_stderr(stderr: str) -> GitHubError:
    """Extract the HTTP status from gh's stderr and build a GitHubError."""
    status = 0
    for line in stderr.splitlines():
        if "HTTP" in line:
            for token in line.split():
                cleaned = token.rstrip(":")
                if cleaned.isdigit() and 100 <= int(cleaned) <= 599:
                    status = int(cleaned)
                    break
            if status:
                break
    return GitHubError(stderr.strip(), status=status)
