#!/usr/bin/env python3
"""Triage Agent - automated triage for LLVM clang-tidy issues."""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from triage_agent import llvm_issues, report_template, triage_db


def _cmd_discover(args: argparse.Namespace) -> int:
    if args.mode == "backlog":
        candidates = llvm_issues.fetch_untagged_clang_tidy_issues()
        # A closed backlog tracking issue means "handled" permanently, not
        # "reconsider me" - the LLVM issue's real labels don't change just
        # because we recommended some, so it would otherwise keep matching
        # the untagged query every day until someone applies them.
        tracked = triage_db.fetch_tracked_llvm_issue_numbers(
            state="all", labels=[triage_db.BACKLOG_TRACKING_LABEL]
        )
    else:
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


def _build_tracking_title(source_title: str, issue_number: int) -> str:
    return f"{source_title} (llvm#{issue_number})"


def _validate_report(args: argparse.Namespace) -> str:
    """Validate report.md against --issue-number and its own fields.

    Shared by every command that consumes a filled-in report.md, since
    they all need the same validated content before deciding what to do
    with it.
    """
    report_markdown = Path(args.report_file).read_text(encoding="utf-8")

    source_issue_number = triage_db.extract_source_issue_number(report_markdown)
    if source_issue_number != args.issue_number:
        raise RuntimeError(
            f"--issue-number {args.issue_number} does not match report.md's "
            f"Source issue #{source_issue_number}"
        )

    unfilled = report_template.find_unfilled_fields(report_markdown)
    if unfilled:
        raise RuntimeError(
            f"report.md for issue {args.issue_number} is incomplete "
            f"(still TBD: {', '.join(unfilled)})"
        )
    report_template.parse_report(args.report_file)  # raises on a bad Verdict/Type
    return report_markdown


def _append_agent_summary_if_present(body: str, args: argparse.Namespace) -> str:
    if args.agent_summary_file:
        summary_path = Path(args.agent_summary_file)
        if summary_path.exists():
            return report_template.append_agent_summary(
                body, summary_path.read_text(encoding="utf-8")
            )
    return body


def _cmd_create_tracking_issue(args: argparse.Namespace) -> int:
    report_markdown = _validate_report(args)
    body = _append_agent_summary_if_present(report_markdown, args)
    source_title = report_template.extract_source_title(report_markdown)
    title = _build_tracking_title(source_title, args.issue_number)
    url = triage_db.create_tracking_issue(
        title=title, body=body, labels=[args.tracking_label]
    )
    print(url)
    return 0


def _cmd_post_comment(args: argparse.Namespace) -> int:
    report_markdown = _validate_report(args)
    analysis = report_template.extract_analysis_section(report_markdown)
    comment_body = _append_agent_summary_if_present(analysis, args)
    url = triage_db.post_comment(
        issue_number=args.comment_issue_number, body=comment_body
    )
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
    discover_parser.add_argument(
        "--mode",
        choices=["recent", "backlog"],
        default="recent",
        help=(
            "'recent' uses --since-days; 'backlog' sweeps older issues "
            "missing all recognized triage labels/Type (default: recent)"
        ),
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
    create_parser.add_argument(
        "--agent-summary-file",
        default=None,
        help=(
            "Optional file with the agent's final chat reply, appended to "
            "the tracking issue as a details block if present and non-empty"
        ),
    )
    create_parser.add_argument(
        "--tracking-label",
        required=True,
        help="Label to apply to the tracking issue (e.g. clang-tidy-triage)",
    )
    create_parser.set_defaults(func=_cmd_create_tracking_issue)


def _add_post_comment_parser(subparsers: argparse._SubParsersAction) -> None:
    comment_parser = subparsers.add_parser(
        "post-comment",
        help="Post a filled-in report.md's Analysis section as a comment on an issue",
    )
    comment_parser.add_argument("--issue-number", type=int, required=True)
    comment_parser.add_argument(
        "--comment-issue-number",
        type=int,
        required=True,
        help="Number of the issue in this repo to post the comment on",
    )
    comment_parser.add_argument(
        "--report-file", default=report_template.REPORT_TEMPLATE_PATH
    )
    comment_parser.add_argument(
        "--agent-summary-file",
        default=None,
        help=(
            "Optional file with the agent's final chat reply, appended to "
            "the comment as a details block if present and non-empty"
        ),
    )
    comment_parser.set_defaults(func=_cmd_post_comment)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="triage-agent",
        description="Automated triage for LLVM clang-tidy issues",
    )
    subparsers = parser.add_subparsers(dest="command")
    _add_discover_parser(subparsers)
    _add_report_template_parser(subparsers)
    _add_create_tracking_issue_parser(subparsers)
    _add_post_comment_parser(subparsers)

    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        return int(args.func(args))

    print("triage-agent: nothing to do yet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
