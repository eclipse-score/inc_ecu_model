# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.

# This program and the accompanying materials are made available under the
# terms of the Apache License Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
# *******************************************************************************

from __future__ import annotations

import argparse
import json
import os
import pickle
from pathlib import Path

from score.parsers.runner.common import _stringify_keys
from score.parsers.runner.load_and_resolve import load_and_resolve


def main() -> None:
    """Merge parser outputs and write the aggregate result."""
    parser = argparse.ArgumentParser(description="Load and resolve parser outputs")
    parser.add_argument(
        "--registry-pickle",
        action="append",
        default=[],
        help="Path to an upstream serialized ModelRegistry pickle",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to output file for parser results",
    )
    parser.add_argument(
        "--text-output",
        type=str,
        default=None,
        help="Path to human-readable text output file",
    )
    args = parser.parse_args()

    output_dump_path = Path(args.output)
    text_dump_path = Path(args.text_output) if args.text_output is not None else None
    if "BUILD_WORKSPACE_DIRECTORY" in os.environ:
        workspace_directory = Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])
        if not output_dump_path.is_absolute():
            output_dump_path = workspace_directory / output_dump_path
        if text_dump_path is not None and not text_dump_path.is_absolute():
            text_dump_path = workspace_directory / text_dump_path

    output_dump_path.parent.mkdir(parents=True, exist_ok=True)
    if text_dump_path is not None:
        text_dump_path.parent.mkdir(parents=True, exist_ok=True)

    result = load_and_resolve(args.registry_pickle)

    with output_dump_path.open("wb") as output_file:
        pickle.dump(result, output_file)

    if text_dump_path is not None:
        text_dump_path.write_text(
            json.dumps(_stringify_keys(result), indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )

    # TBD: resolver, entrance is the selected submodule {datatype, interface, ...} etc

    # pickle dump

if __name__ == "__main__":
    main()
