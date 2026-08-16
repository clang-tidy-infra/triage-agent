#!/usr/bin/env python3
"""Client for the Compiler Explorer (godbolt.org) API.

Used to reproduce clang-tidy warnings reported in LLVM issues without a
local LLVM build: Compiler Explorer hosts a live clang-tidy trunk build
(the "clangtidytrunk" tool) tied to the clang_trunk compiler.
"""

import argparse
import sys
from dataclasses import dataclass
from typing import Any

import requests

GODBOLT_BASE_URL = "https://godbolt.org"
CLANG_TRUNK_COMPILER_ID = "clang_trunk"
CLANG_TIDY_TOOL_ID = "clangtidytrunk"
DEFAULT_TIMEOUT_SECONDS = 60


@dataclass
class ClangTidyResult:
    exit_code: int
    stdout: str
    stderr: str


def _join_lines(lines: list[dict[str, Any]]) -> str:
    return "".join(f"{line['text']}\n" for line in lines)


def _build_compile_payload(
    source: str, tidy_args: str, compiler_args: str
) -> dict[str, Any]:
    return {
        "source": source,
        "options": {
            "userArguments": compiler_args,
            "compilerOptions": {"skipAsm": True},
            "filters": {},
            "tools": [{"id": CLANG_TIDY_TOOL_ID, "args": tidy_args}],
        },
        "lang": "c++",
    }


def run_clang_tidy(
    source: str,
    tidy_args: str,
    compiler_args: str = "",
    compiler_id: str = CLANG_TRUNK_COMPILER_ID,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> ClangTidyResult:
    """Run clang-tidy trunk on `source` via Compiler Explorer's hosted tool."""
    payload = _build_compile_payload(source, tidy_args, compiler_args)
    response = requests.post(
        f"{GODBOLT_BASE_URL}/api/compiler/{compiler_id}/compile",
        json=payload,
        headers={"Accept": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    for tool_result in data.get("tools", []):
        if tool_result.get("id") == CLANG_TIDY_TOOL_ID:
            return ClangTidyResult(
                exit_code=tool_result.get("code", 0),
                stdout=_join_lines(tool_result.get("stdout", [])),
                stderr=_join_lines(tool_result.get("stderr", [])),
            )
    raise RuntimeError(
        f"'{CLANG_TIDY_TOOL_ID}' tool result missing from Compiler Explorer response"
    )


_PLACEHOLDER_SOURCE = "int x;"


def list_checks(
    check_filter: str = "*",
    compiler_id: str = CLANG_TRUNK_COMPILER_ID,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[str]:
    """Return clang-tidy trunk's enabled check names matching `check_filter`.

    Lets callers check whether a proposed new check overlaps with an
    existing one without a local LLVM build. Needs a syntactically
    trivial but non-empty source file; --list-checks output doesn't
    depend on the file's actual contents.
    """
    result = run_clang_tidy(
        _PLACEHOLDER_SOURCE,
        tidy_args=f"--list-checks -checks={check_filter}",
        compiler_id=compiler_id,
        timeout=timeout,
    )
    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and not line.strip().endswith(":")
    ]


def _build_shortener_payload(
    source: str, tidy_args: str, compiler_args: str, compiler_id: str
) -> dict[str, Any]:
    return {
        "sessions": [
            {
                "id": 1,
                "language": "c++",
                "source": source,
                "compilers": [
                    {
                        "id": compiler_id,
                        "options": compiler_args,
                        "tools": [{"id": CLANG_TIDY_TOOL_ID, "args": tidy_args}],
                    }
                ],
            }
        ]
    }


def make_shortlink(
    source: str,
    tidy_args: str,
    compiler_args: str = "",
    compiler_id: str = CLANG_TRUNK_COMPILER_ID,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Create a shareable godbolt.org link reproducing the same session."""
    payload = _build_shortener_payload(source, tidy_args, compiler_args, compiler_id)
    response = requests.post(
        f"{GODBOLT_BASE_URL}/api/shortener",
        json=payload,
        headers={"Accept": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    url: str = response.json()["url"]
    return url


def _read_source(source_file: str | None) -> str:
    if source_file:
        with open(source_file, encoding="utf-8") as f:
            return f.read()
    return sys.stdin.read()


def _add_common_args(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "--source-file", help="Path to the source file (default: read stdin)"
    )
    subparser.add_argument(
        "--tidy-args", default="-checks=*", help="clang-tidy arguments"
    )
    subparser.add_argument("--compiler-args", default="", help="Compiler arguments")
    subparser.add_argument("--compiler-id", default=CLANG_TRUNK_COMPILER_ID)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="godbolt",
        description="Reproduce clang-tidy warnings via Compiler Explorer",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    compile_parser = subparsers.add_parser(
        "compile", help="Run clang-tidy trunk on a source file and print output"
    )
    _add_common_args(compile_parser)

    shortlink_parser = subparsers.add_parser(
        "shortlink", help="Create a shareable godbolt.org link"
    )
    _add_common_args(shortlink_parser)

    list_checks_parser = subparsers.add_parser(
        "list-checks", help="List clang-tidy trunk's enabled check names"
    )
    list_checks_parser.add_argument(
        "--check-filter", default="*", help="Check name glob filter (default: *)"
    )
    list_checks_parser.add_argument("--compiler-id", default=CLANG_TRUNK_COMPILER_ID)

    args = parser.parse_args(argv)

    if args.command == "list-checks":
        for name in list_checks(args.check_filter, args.compiler_id):
            print(name)
        return 0

    source = _read_source(args.source_file)

    if args.command == "compile":
        result = run_clang_tidy(
            source, args.tidy_args, args.compiler_args, args.compiler_id
        )
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        return result.exit_code

    url = make_shortlink(source, args.tidy_args, args.compiler_args, args.compiler_id)
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
