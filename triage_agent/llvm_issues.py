"""Fetch recent clang-tidy-labeled issues from llvm/llvm-project via gh CLI."""

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

LLVM_REPO = "llvm/llvm-project"
CLANG_TIDY_LABEL = "clang-tidy"
ISSUE_JSON_FIELDS = "number,title,body,url,createdAt"
# The primary-bucket triage labels from AGENTS.md's Tags taxonomy - applying
# any one of these (or a GitHub Issue Type) to an LLVM issue is what "this
# issue has been triaged" means elsewhere in this module.
RECOGNIZED_TRIAGE_LABELS = [
    "false-positive",
    "false-negative",
    "enhancement",
    "check-request",
    "documentation",
    "build-problem",
    "code-cleanup",
    "metaissue",
    "question",
]
# Issues missing every recognized triage label and a GitHub Issue Type -
# mirrors the query the user already used manually to find untagged backlog.
UNTAGGED_QUERY = (
    " ".join(f"-label:{label}" for label in RECOGNIZED_TRIAGE_LABELS) + " no:type"
)


@dataclass
class LlvmIssue:
    number: int
    title: str
    body: str
    url: str
    created_at: datetime


def _parse_created_at(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _issue_from_dict(data: dict[str, Any]) -> LlvmIssue:
    return LlvmIssue(
        number=data["number"],
        title=data["title"],
        body=data["body"] or "",
        url=data["url"],
        created_at=_parse_created_at(data["createdAt"]),
    )


def _parse_gh_issue_list_json(raw: str) -> list[LlvmIssue]:
    return [_issue_from_dict(item) for item in json.loads(raw)]


def fetch_recent_clang_tidy_issues(
    since: datetime,
    repo: str = LLVM_REPO,
    label: str = CLANG_TIDY_LABEL,
    limit: int = 300,
) -> list[LlvmIssue]:
    """Fetch open, label-matching issues created at/after `since`, oldest first."""
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
            "open",
            "--json",
            ISSUE_JSON_FIELDS,
            "--limit",
            str(limit),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    issues = _parse_gh_issue_list_json(result.stdout)
    recent = [issue for issue in issues if issue.created_at >= since]
    return sorted(recent, key=lambda issue: issue.created_at)


def fetch_untagged_clang_tidy_issues(
    repo: str = LLVM_REPO,
    label: str = CLANG_TIDY_LABEL,
    limit: int = 500,
) -> list[LlvmIssue]:
    """Open clang-tidy issues missing every recognized triage label and a
    GitHub Issue Type, oldest first - the backlog-sweep discovery mode."""
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
            "open",
            "--search",
            UNTAGGED_QUERY,
            "--json",
            ISSUE_JSON_FIELDS,
            "--limit",
            str(limit),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    issues = _parse_gh_issue_list_json(result.stdout)
    return sorted(issues, key=lambda issue: issue.created_at)


def fetch_issue(number: int, repo: str = LLVM_REPO) -> LlvmIssue:
    """Fetch a single issue by number."""
    result = subprocess.run(
        [
            "gh",
            "issue",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            ISSUE_JSON_FIELDS,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return _issue_from_dict(json.loads(result.stdout))


@dataclass
class LlvmIssueTriageStatus:
    number: int
    state: str  # "OPEN" or "CLOSED"
    labels: list[str]
    has_issue_type: bool


def fetch_issue_triage_status(
    number: int, repo: str = LLVM_REPO
) -> LlvmIssueTriageStatus:
    """Fetch just enough of an LLVM issue to decide `is_issue_triaged` below."""
    result = subprocess.run(
        [
            "gh",
            "issue",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "state,labels,issueType",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    return LlvmIssueTriageStatus(
        number=number,
        state=data["state"],
        labels=[label["name"] for label in data["labels"]],
        has_issue_type=data.get("issueType") is not None,
    )


def is_issue_triaged(status: LlvmIssueTriageStatus) -> bool:
    """True once a maintainer has acted on the LLVM issue - closed it, applied
    a recognized triage label, or set a GitHub Issue Type - meaning a tracking
    issue for it in this repo no longer serves a purpose."""
    if status.state == "CLOSED":
        return True
    if status.has_issue_type:
        return True
    return any(label in RECOGNIZED_TRIAGE_LABELS for label in status.labels)
