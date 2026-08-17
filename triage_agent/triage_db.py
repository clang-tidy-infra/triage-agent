"""Dedup database for LLVM issue triage, built on this repo's own issues.

Each already-triaged LLVM issue has a corresponding tracking issue in
clang-tidy-infra/triage-agent whose body contains report.md's `- **Issue:** <url>`
line (see report_template.py) pointing back at the source LLVM issue.
Dedup works by fetching this repo's tracking issues each run and
regex-extracting that line client-side, deliberately avoiding GitHub's
search-index API (which lags), since a full fetch-and-diff is cheap at
this repo's scale. Both open and closed tracking issues count as tracked
- see `fetch_tracked_llvm_issue_numbers`. To force a re-triage, comment
`/redo` on the tracking issue instead of closing/reopening it.
"""

import json
import re
import subprocess
import tempfile
from pathlib import Path

from triage_agent.llvm_issues import LlvmIssue

TRIAGE_REPO = "clang-tidy-infra/triage-agent"
TRACKING_LABEL = "clang-tidy-triage"
BACKLOG_TRACKING_LABEL = "clang-tidy-triage-backlog"
SOURCE_MARKER_RE = re.compile(
    r"-\s*\*\*Issue:\*\*\s*https://github\.com/llvm/llvm-project/issues/(\d+)"
)


def extract_source_issue_number(body: str) -> int | None:
    """Read the LLVM issue number back out of a `- **Issue:** <url>` line.

    Used both for dedup (scanning this repo's tracking issues) and by
    cli.py to cross-check that a report.md's embedded issue matches the
    --issue-number it's being filed under.
    """
    match = SOURCE_MARKER_RE.search(body)
    return int(match.group(1)) if match else None


def fetch_tracked_llvm_issue_numbers(
    repo: str = TRIAGE_REPO, state: str = "all", labels: list[str] | None = None
) -> set[int]:
    """Return LLVM issue numbers with a tracking issue in this repo.

    `state="all"` (the default) means a closed tracking issue is a
    permanent "handled" marker, not a signal to redo it - closing an
    issue and having the bot silently recreate it later would be
    surprising. Reprocessing an already-tracked issue must be requested
    explicitly, either via the manual --issue-number override or by
    commenting `/redo` on its tracking issue.

    `labels` defaults to `[TRACKING_LABEL]`. Passing multiple labels unions
    their results (one `gh issue list` call per label) rather than
    intersecting, since `--label` on a single call is an AND filter and
    tracking issues only ever carry one of these labels, never both.
    """
    if labels is None:
        labels = [TRACKING_LABEL]
    numbers: set[int] = set()
    for label in labels:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "list",
                "--repo",
                repo,
                "--label",
                label,
                "--state",
                state,
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
        numbers.update(
            number
            for number in (
                extract_source_issue_number(issue["body"] or "") for issue in issues
            )
            if number is not None
        )
    return numbers


def select_new_issues(
    llvm_issues: list[LlvmIssue], tracked: set[int], cap: int = 5
) -> list[LlvmIssue]:
    """Filter out already-tracked issues, oldest-first, capped at `cap`."""
    untracked = [issue for issue in llvm_issues if issue.number not in tracked]
    ordered = sorted(untracked, key=lambda issue: issue.created_at)
    return ordered[:cap]


def create_tracking_issue(
    title: str,
    body: str,
    repo: str = TRIAGE_REPO,
    labels: list[str] | None = None,
) -> str:
    """Create a tracking issue in `repo` and return its URL."""
    if labels is None:
        labels = [TRACKING_LABEL]
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as body_file:
        body_file.write(body)
        body_path = body_file.name
    try:
        argv = [
            "gh",
            "issue",
            "create",
            "--repo",
            repo,
            "--title",
            title,
            "--body-file",
            body_path,
        ]
        for label in labels:
            argv += ["--label", label]
        result = subprocess.run(argv, check=True, capture_output=True, text=True)
    finally:
        Path(body_path).unlink()
    return result.stdout.strip()


def post_comment(issue_number: int, body: str, repo: str = TRIAGE_REPO) -> str:
    """Post a comment on an existing issue in `repo` and return its URL."""
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
                "comment",
                str(issue_number),
                "--repo",
                repo,
                "--body-file",
                body_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        Path(body_path).unlink()
    return result.stdout.strip()
