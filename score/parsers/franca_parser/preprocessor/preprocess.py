# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
# *******************************************************************************

"""A small textual preprocessor for Franca conditional compilation."""

import argparse
import re
from pathlib import Path

IF_RE = re.compile(r"^\s*#if\s+defined\s+([A-Za-z_][A-Za-z0-9_]*)")
ELIF_RE = re.compile(r"^\s*#elif\s+defined\s+([A-Za-z_][A-Za-z0-9_]*)")
ELSE_RE = re.compile(r"^\s*#else\b")
END_RE = re.compile(r"^\s*#endif\b")


class PreProcessError(Exception):
    """Raised when a preprocessing directive is malformed or unsupported."""


def parse_args():
    """Parse command-line options for preprocessing.

    :return: The parsed command-line options.
    """
    parser = argparse.ArgumentParser(description="Flat #if/#elif/#else pre-processor")
    parser.add_argument("-D", dest="defines", action="append", default=[], help="Define symbol (repeat as needed)")
    parser.add_argument("-o", "--output", required=True, type=Path, help="Output file")
    parser.add_argument("-i", "--input-src", type=Path, help="Input source file")
    return parser.parse_args()


def preprocess(content: str, defines: set[str]) -> str:
    """Keep source lines selected by supported conditional directives.

    :param content: Source text containing conditional directives.
    :param defines: Symbols treated as defined when evaluating directives.
    :return: Source text with directives and inactive lines removed.
    """
    lines = content.splitlines(keepends=True)
    output_lines = []

    in_if = False
    active = True
    taken = False

    for lineno, line in enumerate(lines, start=1):
        match = IF_RE.match(line)
        if match:
            if in_if:
                raise PreProcessError(f"Unsupported nested #if, line {lineno}")
            in_if = True
            symbol = match.group(1)
            active = symbol in defines
            taken = active
            continue

        match = ELIF_RE.match(line)
        if match:
            if not in_if:
                raise PreProcessError(f"#elif without previous #if, line {lineno}")
            if taken:
                active = False
            else:
                symbol = match.group(1)
                active = symbol in defines
                taken = active
            continue

        if ELSE_RE.match(line):
            if not in_if:
                raise PreProcessError(f"#else without previous #if, line {lineno}")
            active = not taken
            taken = True
            continue

        if END_RE.match(line):
            if not in_if:
                raise PreProcessError(f"#endif without previous #if, line {lineno}")
            in_if = False
            active = True
            taken = False
            continue

        if active:
            output_lines.append(line)

    if in_if:
        raise PreProcessError("Non terminated #if block")

    return "".join(output_lines)


def main() -> None:
    """Read, preprocess, and write the files specified on the command line."""
    args = parse_args()
    defines = set(args.defines)

    input_text = args.input_src.read_text(encoding="utf-8")
    output_text = preprocess(input_text, defines)
    args.output.write_text(output_text, encoding="utf-8")


if __name__ == "__main__":
    main()
