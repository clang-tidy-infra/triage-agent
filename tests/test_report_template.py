import tempfile
import unittest
from pathlib import Path

from triage_agent import triage_db
from triage_agent.report_template import (
    ReportTemplateInputs,
    append_agent_summary,
    extract_analysis_section,
    extract_source_title,
    find_unfilled_fields,
    generate_report_template,
    parse_report,
)

INPUTS = ReportTemplateInputs(
    llvm_issue_url="https://github.com/llvm/llvm-project/issues/12345",
    llvm_issue_title="[clang-tidy] some-check false positive",
    llvm_issue_body="```cpp\nint x = 0;\n```",
)


class TestGenerateReportTemplate(unittest.TestCase):
    def test_writes_metadata_and_tbd_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = str(Path(tmp) / "report.md")
            generate_report_template(INPUTS, output=output)
            content = Path(output).read_text(encoding="utf-8")

        self.assertTrue(content.startswith("## Source"))
        self.assertIn(INPUTS.llvm_issue_url, content)
        self.assertIn(INPUTS.llvm_issue_title, content)
        self.assertIn(INPUTS.llvm_issue_body, content)
        self.assertIn("**Verdict:** TBD", content)
        self.assertIn("**Type:** TBD", content)
        self.assertIn("**Tags:** TBD", content)
        self.assertIn("**Godbolt Link:** TBD", content)
        self.assertIn("**Rationale:** TBD", content)

    def test_extract_source_issue_number_finds_issue_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = str(Path(tmp) / "report.md")
            generate_report_template(INPUTS, output=output)
            content = Path(output).read_text(encoding="utf-8")

        self.assertEqual(triage_db.extract_source_issue_number(content), 12345)


class TestParseReport(unittest.TestCase):
    def _write(self, tmp: str, body: str) -> str:
        path = str(Path(tmp) / "report.md")
        Path(path).write_text(body, encoding="utf-8")
        return path

    def test_parses_filled_in_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                "- **Verdict:** Reproduced\n"
                "- **Type:** Bug\n"
                "- **Tags:** false-positive, confirmed\n"
                "- **Godbolt Link:** https://godbolt.org/z/abc123\n"
                "- **Rationale:** This is a real false positive because\n"
                "  the check misfires on templates.\n",
            )
            parsed = parse_report(path)

        self.assertEqual(parsed.verdict, "Reproduced")
        self.assertEqual(parsed.issue_type, "Bug")
        self.assertEqual(parsed.tags, "false-positive, confirmed")
        self.assertEqual(parsed.godbolt_link, "https://godbolt.org/z/abc123")
        self.assertIn("misfires on templates.", parsed.rationale)

    def test_treats_na_godbolt_link_as_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                "- **Verdict:** Uncertain\n"
                "- **Type:** Task\n"
                "- **Tags:** question\n"
                "- **Godbolt Link:** N/A\n"
                "- **Rationale:** No reproducible snippet in the issue body.\n",
            )
            parsed = parse_report(path)

        self.assertIsNone(parsed.godbolt_link)

    def test_accepts_feature_and_question_verdicts(self):
        for verdict in ("New Check Proposal", "Enhancement Request", "Question"):
            with self.subTest(verdict=verdict):
                with tempfile.TemporaryDirectory() as tmp:
                    path = self._write(
                        tmp,
                        f"- **Verdict:** {verdict}\n"
                        "- **Type:** Feature\n"
                        "- **Tags:** check-request\n"
                        "- **Godbolt Link:** N/A\n"
                        "- **Rationale:** investigated via the local checkout.\n",
                    )
                    parsed = parse_report(path)

                self.assertEqual(parsed.verdict, verdict)

    def test_raises_on_unrecognized_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                "- **Verdict:** Reproduced\n"
                "- **Type:** Defect\n"
                "- **Tags:** false-positive\n"
                "- **Godbolt Link:** N/A\n"
                "- **Rationale:** garbled output.\n",
            )
            with self.assertRaises(ValueError):
                parse_report(path)

    def test_raises_on_unrecognized_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                "- **Verdict:** Reproduced\n"
                "- **Type:** Bug\n"
                "- **Tags:** flase-positive\n"
                "- **Godbolt Link:** N/A\n"
                "- **Rationale:** garbled output.\n",
            )
            with self.assertRaises(ValueError):
                parse_report(path)

    def test_raises_when_confirmed_paired_with_not_reproduced(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                "- **Verdict:** Not Reproduced\n"
                "- **Type:** Bug\n"
                "- **Tags:** false-positive, confirmed\n"
                "- **Godbolt Link:** N/A\n"
                "- **Rationale:** no longer warns on trunk.\n",
            )
            with self.assertRaises(ValueError):
                parse_report(path)

    def test_accepts_multiple_known_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                "- **Verdict:** Crash\n"
                "- **Type:** Bug\n"
                "- **Tags:** crash-on-valid, confirmed\n"
                "- **Godbolt Link:** N/A\n"
                "- **Rationale:** crashes on trunk.\n",
            )
            parsed = parse_report(path)

        self.assertEqual(parsed.tags, "crash-on-valid, confirmed")

    def test_accepts_na_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                "- **Verdict:** Uncertain\n"
                "- **Type:** Task\n"
                "- **Tags:** N/A\n"
                "- **Godbolt Link:** N/A\n"
                "- **Rationale:** nothing applies.\n",
            )
            parsed = parse_report(path)

        self.assertEqual(parsed.tags, "N/A")

    def test_raises_when_field_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "- **Godbolt Link:** N/A\n")
            with self.assertRaises(ValueError):
                parse_report(path)

    def test_raises_on_unrecognized_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                "- **Verdict:** probably reproduced maybe\n"
                "- **Godbolt Link:** N/A\n"
                "- **Rationale:** garbled output.\n",
            )
            with self.assertRaises(ValueError):
                parse_report(path)

    def test_extracts_godbolt_link_wrapped_onto_next_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                "- **Verdict:** Reproduced\n"
                "- **Type:** Bug\n"
                "- **Tags:** false-positive\n"
                "- **Godbolt Link:**\n"
                "  https://godbolt.org/z/abc123\n"
                "- **Rationale:** because.\n",
            )
            parsed = parse_report(path)

        self.assertEqual(parsed.godbolt_link, "https://godbolt.org/z/abc123")


class TestFindUnfilledFields(unittest.TestCase):
    def test_finds_no_unfilled_fields_when_all_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = str(Path(tmp) / "report.md")
            generate_report_template(INPUTS, output=output)
            content = Path(output).read_text(encoding="utf-8")
            content = content.replace("TBD", "filled in")

        self.assertEqual(find_unfilled_fields(content), [])

    def test_finds_all_fields_unfilled_in_fresh_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = str(Path(tmp) / "report.md")
            generate_report_template(INPUTS, output=output)
            content = Path(output).read_text(encoding="utf-8")

        self.assertEqual(
            find_unfilled_fields(content),
            [
                "Check Name",
                "Extracted Snippet",
                "Flags/Config",
                "Verdict",
                "Type",
                "Tags",
                "Godbolt Link",
                "Rationale",
            ],
        )

    def test_finds_only_the_one_field_left_tbd(self):
        content = (
            "- **Check Name:** bugprone-foo\n"
            "- **Extracted Snippet:** ```cpp\\nint x;\\n```\n"
            "- **Flags/Config:** -checks=-*,bugprone-foo\n"
            "- **Verdict:** TBD\n"
            "- **Type:** Bug\n"
            "- **Tags:** false-positive\n"
            "- **Godbolt Link:** N/A\n"
            "- **Rationale:** still deciding.\n"
        )

        self.assertEqual(find_unfilled_fields(content), ["Verdict"])


class TestExtractSourceTitle(unittest.TestCase):
    def test_extracts_title_from_generated_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = str(Path(tmp) / "report.md")
            generate_report_template(INPUTS, output=output)
            content = Path(output).read_text(encoding="utf-8")

        self.assertEqual(extract_source_title(content), INPUTS.llvm_issue_title)


class TestExtractAnalysisSection(unittest.TestCase):
    def test_drops_source_section(self):
        content = (
            "## Source\n\n- **Issue:** https://github.com/llvm/llvm-project/issues/1\n"
            "- **Title:** some-check false positive\n\n"
            "## Analysis\n\n- **Verdict:** Reproduced\n- **Type:** Bug\n"
        )

        result = extract_analysis_section(content)

        self.assertTrue(result.startswith("## Analysis"))
        self.assertNotIn("## Source", result)
        self.assertIn("**Verdict:** Reproduced", result)

    def test_raises_when_analysis_section_missing(self):
        with self.assertRaises(ValueError):
            extract_analysis_section("## Source\n\nno analysis here\n")

    def test_uses_last_occurrence_when_source_quotes_a_fake_heading(self):
        content = (
            "## Source\n\n"
            "- **Issue:** https://github.com/llvm/llvm-project/issues/1\n"
            "- **Title:** t\n\n"
            "<details>\n<summary>Original issue body</summary>\n\n"
            "## Analysis\nThe reporter pasted a fake heading here.\n\n"
            "</details>\n\n"
            "## Analysis\n\n- **Verdict:** Reproduced\n"
        )

        result = extract_analysis_section(content)

        self.assertEqual(result, "## Analysis\n\n- **Verdict:** Reproduced")


class TestAppendAgentSummary(unittest.TestCase):
    def test_wraps_summary_in_details_block(self):
        body = append_agent_summary("report body", "**Summary:** it's a bug.")

        self.assertTrue(body.startswith("report body\n"))
        self.assertIn("<details>", body)
        self.assertIn("<summary><b>Agent Summary</b>", body)
        self.assertIn("**Summary:** it's a bug.", body)
        self.assertTrue(body.rstrip().endswith("</details>"))

    def test_strips_surrounding_whitespace(self):
        body = append_agent_summary("report body", "\n\n  **Summary:** ok.  \n\n")

        self.assertIn("**Summary:** ok.\n\n</details>", body)

    def test_returns_body_unchanged_when_summary_blank(self):
        self.assertEqual(append_agent_summary("report body", "   \n  "), "report body")
        self.assertEqual(append_agent_summary("report body", ""), "report body")


if __name__ == "__main__":
    unittest.main()
