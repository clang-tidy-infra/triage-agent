import tempfile
import unittest
from pathlib import Path

from triage_agent import triage_db
from triage_agent.report_template import (
    ReportTemplateInputs,
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
        self.assertIn("**Godbolt Link:** TBD", content)
        self.assertIn("**Rationale:** TBD", content)

    def test_extract_source_issue_number_finds_issue_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = str(Path(tmp) / "report.md")
            generate_report_template(INPUTS, output=output)
            content = Path(output).read_text(encoding="utf-8")

        self.assertEqual(triage_db._extract_source_issue_number(content), 12345)


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
                "- **Godbolt Link:** https://godbolt.org/z/abc123\n"
                "- **Rationale:** This is a real false positive because\n"
                "  the check misfires on templates.\n",
            )
            parsed = parse_report(path)

        self.assertEqual(parsed.verdict, "Reproduced")
        self.assertEqual(parsed.godbolt_link, "https://godbolt.org/z/abc123")
        self.assertIn("misfires on templates.", parsed.rationale)

    def test_treats_na_godbolt_link_as_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                "- **Verdict:** Uncertain\n"
                "- **Godbolt Link:** N/A\n"
                "- **Rationale:** No reproducible snippet in the issue body.\n",
            )
            parsed = parse_report(path)

        self.assertIsNone(parsed.godbolt_link)

    def test_raises_when_field_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "- **Godbolt Link:** N/A\n")
            with self.assertRaises(ValueError):
                parse_report(path)


if __name__ == "__main__":
    unittest.main()
