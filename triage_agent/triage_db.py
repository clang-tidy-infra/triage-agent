"""Dedup database for LLVM issue triage, built on this repo's own issues.

Each already-triaged LLVM issue has a corresponding tracking issue in
vbvictor/triage-agent whose body contains a `**Source:** <url>` marker
line. Dedup works by fetching ALL of this repo's issues each run and
regex-extracting those markers client-side, deliberately avoiding
GitHub's search-index API (which lags), since a full fetch-and-diff is
cheap at this repo's scale.
"""

import json
import re
import subprocess
import tempfile
from pathlib import Path

from triage_agent.llvm_issues import LlvmIssue

TRIAGE_REPO = "vbvictor/triage-agent"
TRACKING_LABEL = "clang-tidy-triage"
SOURCE_MARKER_RE = re.compile(
    r"\*\*Source:\*\*\s*(https://github\.com/llvm/llvm-project/issues/(\d+))"
)


def _extract_source_issue_number(body: str) -> int | None:
    match = SOURCE_MARKER_RE.search(body)
    return int(match.group(2)) if match else None


def fetch_tracked_llvm_issue_numbers(repo: str = TRIAGE_REPO) -> set[int]:
    """Return the set of LLVM issue numbers already tracked by this repo."""
    result = subprocess.run(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--json",
            "title,body",
            "--limit",
            "1000",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    issues = json.loads(result.stdout)
    numbers = (_extract_source_issue_number(issue["body"] or "") for issue in issues)
    return {number for number in numbers if number is not None}


def select_new_issues(
    llvm_issues: list[LlvmIssue], tracked: set[int], cap: int = 5
) -> list[LlvmIssue]:
    """Filter out already-tracked issues, oldest-first, capped at `cap`."""
    untracked = [issue for issue in llvm_issues if issue.number not in tracked]
    ordered = sorted(untracked, key=lambda issue: issue.created_at)
    return ordered[:cap]


def build_source_marker(llvm_issue_url: str) -> str:
    return f"**Source:** {llvm_issue_url}"


def create_tracking_issue(
    title: str, body: str, repo: str = TRIAGE_REPO, label: str = TRACKING_LABEL
) -> str:
    """Create a tracking issue in `repo` and return its URL."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as body_file:
        body_file.write(body)
        body_path = body_file.name
    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "create",
                "--repo",
                repo,
                "--title",
                title,
                "--body-file",
                body_path,
                "--label",
                label,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        Path(body_path).unlink()
    return result.stdout.strip()
