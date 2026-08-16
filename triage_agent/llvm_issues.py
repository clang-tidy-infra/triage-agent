"""Fetch recent clang-tidy-labeled issues from llvm/llvm-project via gh CLI."""

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

LLVM_REPO = "llvm/llvm-project"
CLANG_TIDY_LABEL = "clang-tidy"
ISSUE_JSON_FIELDS = "number,title,body,url,createdAt"


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
    """Fetch label-matching issues created at/after `since`, oldest first."""
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
            "all",
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
