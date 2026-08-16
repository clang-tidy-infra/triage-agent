import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from triage_agent import cli, main
from triage_agent.llvm_issues import LlvmIssue
from triage_agent.report_template import ParsedReport


def _issue(number: int) -> LlvmIssue:
    return LlvmIssue(
        number=number,
        title="t",
        body="b",
        url=f"https://github.com/llvm/llvm-project/issues/{number}",
        created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )


class TestMain(unittest.TestCase):
    def test_returns_zero(self):
        self.assertEqual(main([]), 0)


class TestDiscoverCommand(unittest.TestCase):
    @patch("triage_agent.triage_db.select_new_issues")
    @patch("triage_agent.triage_db.fetch_tracked_llvm_issue_numbers")
    @patch("triage_agent.llvm_issues.fetch_recent_clang_tidy_issues")
    def test_prints_json_array_of_selected_issue_numbers(
        self, mock_fetch, mock_tracked, mock_select
    ):
        mock_fetch.return_value = [_issue(1), _issue(2)]
        mock_tracked.return_value = {1}
        mock_select.return_value = [_issue(2)]

        with patch("builtins.print") as mock_print:
            exit_code = main(["discover", "--since-days", "3", "--cap", "1"])

        self.assertEqual(exit_code, 0)
        mock_fetch.assert_called_once()
        mock_select.assert_called_once_with(mock_fetch.return_value, {1}, cap=1)
        mock_print.assert_called_once_with("[2]")


class TestReportTemplateCommand(unittest.TestCase):
    @patch("triage_agent.report_template.generate_report_template")
    @patch("triage_agent.llvm_issues.fetch_issue")
    def test_generates_template_for_fetched_issue(self, mock_fetch, mock_generate):
        mock_fetch.return_value = _issue(42)

        exit_code = main(
            ["report-template", "--issue-number", "42", "--output", "out.md"]
        )

        self.assertEqual(exit_code, 0)
        mock_fetch.assert_called_once_with(42)
        args, kwargs = mock_generate.call_args
        self.assertEqual(args[0].llvm_issue_url, _issue(42).url)
        self.assertEqual(kwargs["output"], "out.md")


class TestBuildTrackingTitle(unittest.TestCase):
    def test_appends_issue_number(self):
        self.assertEqual(
            cli._build_tracking_title("[clang-tidy] some-check false positive", 42),
            "[clang-tidy] some-check false positive (llvm#42)",
        )


class TestCreateTrackingIssueCommand(unittest.TestCase):
    @patch("triage_agent.triage_db.create_tracking_issue")
    @patch("triage_agent.report_template.extract_source_title")
    @patch("triage_agent.report_template.parse_report")
    @patch("triage_agent.report_template.find_unfilled_fields")
    @patch("triage_agent.triage_db.extract_source_issue_number")
    def test_creates_issue_when_report_complete(
        self,
        mock_source_number,
        mock_unfilled,
        mock_parse,
        mock_extract_title,
        mock_create,
    ):
        mock_source_number.return_value = 42
        mock_unfilled.return_value = []
        mock_parse.return_value = ParsedReport(
            verdict="Reproduced",
            issue_type="Bug",
            tags="false-positive, confirmed",
            rationale="because",
            godbolt_link="https://godbolt.org/z/x",
        )
        mock_extract_title.return_value = "some-check false positive"
        mock_create.return_value = "https://github.com/vbvictor/triage-agent/issues/1"

        with (
            patch("triage_agent.cli.Path.read_text", return_value="report contents"),
            patch("builtins.print") as mock_print,
        ):
            exit_code = main(
                [
                    "create-tracking-issue",
                    "--issue-number",
                    "42",
                    "--report-file",
                    "r.md",
                ]
            )

        self.assertEqual(exit_code, 0)
        mock_create.assert_called_once_with(
            title="some-check false positive (llvm#42)", body="report contents"
        )
        mock_print.assert_called_once_with(
            "https://github.com/vbvictor/triage-agent/issues/1"
        )

    @patch("triage_agent.report_template.find_unfilled_fields")
    @patch("triage_agent.triage_db.extract_source_issue_number")
    def test_raises_when_fields_still_tbd(self, mock_source_number, mock_unfilled):
        mock_source_number.return_value = 42
        mock_unfilled.return_value = ["Verdict", "Rationale"]

        with (
            patch("triage_agent.cli.Path.read_text", return_value="report contents"),
            self.assertRaises(RuntimeError),
        ):
            main(["create-tracking-issue", "--issue-number", "42"])

    @patch("triage_agent.report_template.parse_report")
    @patch("triage_agent.report_template.find_unfilled_fields")
    @patch("triage_agent.triage_db.extract_source_issue_number")
    def test_raises_when_verdict_invalid(
        self, mock_source_number, mock_unfilled, mock_parse
    ):
        mock_source_number.return_value = 42
        mock_unfilled.return_value = []
        mock_parse.side_effect = ValueError("bad verdict")

        with (
            patch("triage_agent.cli.Path.read_text", return_value="report contents"),
            self.assertRaises(ValueError),
        ):
            main(["create-tracking-issue", "--issue-number", "42"])

    @patch("triage_agent.report_template.find_unfilled_fields")
    @patch("triage_agent.triage_db.extract_source_issue_number")
    def test_raises_when_issue_number_mismatches_report(
        self, mock_source_number, mock_unfilled
    ):
        mock_source_number.return_value = 99

        with (
            patch("triage_agent.cli.Path.read_text", return_value="report contents"),
            self.assertRaises(RuntimeError),
        ):
            main(["create-tracking-issue", "--issue-number", "42"])

        mock_unfilled.assert_not_called()


if __name__ == "__main__":
    unittest.main()
