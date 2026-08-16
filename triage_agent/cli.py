#!/usr/bin/env python3
"""Triage Agent - automated triage for LLVM clang-tidy issues."""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from triage_agent import llvm_issues, report_template, triage_db


def _cmd_discover(args: argparse.Namespace) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=args.since_days)
    candidates = llvm_issues.fetch_recent_clang_tidy_issues(since)
    tracked = triage_db.fetch_tracked_llvm_issue_numbers()
    new_issues = triage_db.select_new_issues(candidates, tracked, cap=args.cap)
    print(json.dumps([issue.number for issue in new_issues]))
    return 0


def _cmd_report_template(args: argparse.Namespace) -> int:
    issue = llvm_issues.fetch_issue(args.issue_number)
    inputs = report_template.ReportTemplateInputs(
        llvm_issue_url=issue.url,
        llvm_issue_title=issue.title,
        llvm_issue_body=issue.body,
    )
    report_template.generate_report_template(inputs, output=args.output)
    return 0


def _build_tracking_title(issue: llvm_issues.LlvmIssue) -> str:
    return f"{issue.title} (llvm#{issue.number})"


def _cmd_create_tracking_issue(args: argparse.Namespace) -> int:
    issue = llvm_issues.fetch_issue(args.issue_number)
    report_markdown = Path(args.report_file).read_text(encoding="utf-8")
    parsed = report_template.parse_report(args.report_file)
    if parsed.verdict.strip().upper() == report_template.TBD:
        raise RuntimeError(
            f"report.md for issue {args.issue_number} was not filled in "
            "(Verdict is still TBD)"
        )
    title = _build_tracking_title(issue)
    url = triage_db.create_tracking_issue(title=title, body=report_markdown)
    print(url)
    return 0


def _add_discover_parser(subparsers: argparse._SubParsersAction) -> None:
    discover_parser = subparsers.add_parser(
        "discover", help="Find new clang-tidy LLVM issues to triage"
    )
    discover_parser.add_argument(
        "--since-days",
        type=int,
        default=7,
        help="Only consider issues created within this many days (default: 7)",
    )
    discover_parser.add_argument(
        "--cap",
        type=int,
        default=1,
        help="Maximum number of issues to select per run (default: 1)",
    )
    discover_parser.set_defaults(func=_cmd_discover)


def _add_report_template_parser(subparsers: argparse._SubParsersAction) -> None:
    report_template_parser = subparsers.add_parser(
        "report-template", help="Generate report.md for a single LLVM issue"
    )
    report_template_parser.add_argument("--issue-number", type=int, required=True)
    report_template_parser.add_argument(
        "--output", default=report_template.REPORT_TEMPLATE_PATH
    )
    report_template_parser.set_defaults(func=_cmd_report_template)


def _add_create_tracking_issue_parser(subparsers: argparse._SubParsersAction) -> None:
    create_parser = subparsers.add_parser(
        "create-tracking-issue",
        help="Create a triage-agent issue from a filled-in report.md",
    )
    create_parser.add_argument("--issue-number", type=int, required=True)
    create_parser.add_argument(
        "--report-file", default=report_template.REPORT_TEMPLATE_PATH
    )
    create_parser.set_defaults(func=_cmd_create_tracking_issue)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="triage-agent",
        description="Automated triage for LLVM clang-tidy issues",
    )
    subparsers = parser.add_subparsers(dest="command")
    _add_discover_parser(subparsers)
    _add_report_template_parser(subparsers)
    _add_create_tracking_issue_parser(subparsers)

    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        return int(args.func(args))

    print("triage-agent: nothing to do yet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
