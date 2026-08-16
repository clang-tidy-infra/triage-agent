"""Generates and parses report.md, the file a single agent run edits in
place to analyze one LLVM clang-tidy issue.

The metadata section (source URL/title/raw issue body) is fixed and must
not be touched by the agent; the analysis fields below it are TBD
placeholders the agent fills in, per AGENTS.md.
"""

import re
from dataclasses import dataclass
from pathlib import Path

REPORT_TEMPLATE_PATH = "report.md"
TBD = "TBD"
NOT_APPLICABLE = "N/A"


@dataclass
class ReportTemplateInputs:
    llvm_issue_url: str
    llvm_issue_title: str
    llvm_issue_body: str


def generate_report_template(
    inputs: ReportTemplateInputs, output: str = REPORT_TEMPLATE_PATH
) -> None:
    content = f"""\
## Source

- **Issue:** {inputs.llvm_issue_url}
- **Title:** {inputs.llvm_issue_title}

<details>
<summary>Original issue body</summary>

{inputs.llvm_issue_body}

</details>

## Analysis

- **Check Name:** {TBD}
- **Extracted Snippet:** {TBD}
- **Flags/Config:** {TBD}
- **Verdict:** {TBD}
- **Godbolt Link:** {TBD}
- **Rationale:** {TBD}
"""
    Path(output).write_text(content, encoding="utf-8")


@dataclass
class ParsedReport:
    verdict: str
    rationale: str
    godbolt_link: str | None


def _extract_field(content: str, name: str) -> str:
    match = re.search(rf"^- \*\*{re.escape(name)}:\*\*\s*(.*)$", content, re.MULTILINE)
    if not match:
        raise ValueError(f"report.md missing required field: {name}")
    return match.group(1).strip()


def _extract_rationale(content: str) -> str:
    match = re.search(
        r"^- \*\*Rationale:\*\*\s*(.*)", content, re.MULTILINE | re.DOTALL
    )
    if not match:
        raise ValueError("report.md missing required field: Rationale")
    return match.group(1).strip()


def parse_report(path: str = REPORT_TEMPLATE_PATH) -> ParsedReport:
    content = Path(path).read_text(encoding="utf-8")
    godbolt_link = _extract_field(content, "Godbolt Link")
    return ParsedReport(
        verdict=_extract_field(content, "Verdict"),
        rationale=_extract_rationale(content),
        godbolt_link=(
            None if godbolt_link.upper() in {NOT_APPLICABLE, TBD, ""} else godbolt_link
        ),
    )
