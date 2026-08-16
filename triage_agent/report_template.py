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
ANALYSIS_FIELDS = [
    "Check Name",
    "Extracted Snippet",
    "Flags/Config",
    "Verdict",
    "Type",
    "Tags",
    "Godbolt Link",
    "Rationale",
]
KNOWN_VERDICTS = {"Reproduced", "Not Reproduced", "Crash", "Uncertain"}
# GitHub's org-level Issue Types for llvm/llvm-project - see AGENTS.md for
# the full recommended-Tags taxonomy (kept there since it's a longer list
# with descriptions, not something code needs to validate against).
KNOWN_TYPES = {"Bug", "Feature", "Task"}


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
- **Type:** {TBD}
- **Tags:** {TBD}
- **Godbolt Link:** {TBD}
- **Rationale:** {TBD}
"""
    Path(output).write_text(content, encoding="utf-8")


@dataclass
class ParsedReport:
    verdict: str
    issue_type: str
    tags: str
    rationale: str
    godbolt_link: str | None


def _extract_field(content: str, name: str) -> str:
    match = re.search(
        rf"^- \*\*{re.escape(name)}:\*\*[ \t]*(.*)$", content, re.MULTILINE
    )
    if not match:
        raise ValueError(f"report.md missing required field: {name}")
    value = match.group(1).strip()
    if value:
        return value
    # The agent may have wrapped a long value (e.g. a URL) onto the next
    # line instead of writing it inline after the label.
    next_line_match = re.search(r"\n[ \t]*(\S[^\n]*)", content[match.end() :])
    if next_line_match and not next_line_match.group(1).startswith("- **"):
        return next_line_match.group(1).strip()
    return value


def _extract_rationale(content: str) -> str:
    match = re.search(
        r"^- \*\*Rationale:\*\*\s*(.*)", content, re.MULTILINE | re.DOTALL
    )
    if not match:
        raise ValueError("report.md missing required field: Rationale")
    return match.group(1).strip()


def extract_source_title(content: str) -> str:
    """Read the LLVM issue's title back out of report.md's Source section."""
    return _extract_field(content, "Title")


def find_unfilled_fields(content: str) -> list[str]:
    """Return the names of any Analysis fields the agent left as TBD."""
    return [
        field
        for field in ANALYSIS_FIELDS
        if re.search(
            rf"^- \*\*{re.escape(field)}:\*\*\s*{TBD}\s*$", content, re.MULTILINE
        )
    ]


def parse_report(path: str = REPORT_TEMPLATE_PATH) -> ParsedReport:
    content = Path(path).read_text(encoding="utf-8")
    verdict = _extract_field(content, "Verdict")
    if verdict.upper() != TBD and verdict not in KNOWN_VERDICTS:
        raise ValueError(
            f"Unrecognized verdict {verdict!r}; expected one of "
            f"{sorted(KNOWN_VERDICTS)}"
        )
    issue_type = _extract_field(content, "Type")
    if issue_type.upper() != TBD and issue_type not in KNOWN_TYPES:
        raise ValueError(
            f"Unrecognized issue type {issue_type!r}; expected one of "
            f"{sorted(KNOWN_TYPES)}"
        )
    godbolt_link = _extract_field(content, "Godbolt Link")
    return ParsedReport(
        verdict=verdict,
        issue_type=issue_type,
        tags=_extract_field(content, "Tags"),
        rationale=_extract_rationale(content),
        godbolt_link=(
            None if godbolt_link.upper() in {NOT_APPLICABLE, TBD, ""} else godbolt_link
        ),
    )
