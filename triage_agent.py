#!/usr/bin/env python3
"""Triage Agent - automated triage for LLVM clang-tidy issues."""

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="triage-agent",
        description="Automated triage for LLVM clang-tidy issues",
    )
    parser.parse_args(argv)
    print("triage-agent: nothing to do yet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
