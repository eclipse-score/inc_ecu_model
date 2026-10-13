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
from dataclasses import fields, is_dataclass
import json
import os
import pickle
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from score.parsers.runner.common import ParsingPathInfo
from score.parsers.runner.load_dispatch import load_and_parse

def _stringify_keys(obj: Any, active_object_ids: set[int] | None = None) -> Any:
    """Convert nested values into a JSON-friendly structure and mark cycles.

    :param obj: Value to expand into JSON-compatible containers.
    :param active_object_ids: Object identities on the current traversal path.
    :return: Expanded value, with cyclic references represented by an ellipsis marker.
    """
    if active_object_ids is None:
        active_object_ids = set()

    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj

    object_id = id(obj)
    if object_id in active_object_ids:
        return "..."
    active_object_ids.add(object_id)

    try:
        if isinstance(obj, dict):
            return {
                str(key): _stringify_keys(value, active_object_ids)
                for key, value in obj.items()
            }
        if isinstance(obj, (list, tuple, set, frozenset)):
            return [_stringify_keys(value, active_object_ids) for value in obj]
        if is_dataclass(obj) and not isinstance(obj, type):
            return {
                field.name: _stringify_keys(getattr(obj, field.name), active_object_ids)
                for field in fields(obj)
            }
        if isinstance(obj, BaseModel):
            model_fields = getattr(type(obj), "model_fields", None)
            if model_fields is None:
                model_fields = getattr(type(obj), "__fields__", {})
            return {
                field_name: _stringify_keys(getattr(obj, field_name), active_object_ids)
                for field_name in model_fields
            }
        if hasattr(obj, "__dict__"):
            return {
                str(key): _stringify_keys(value, active_object_ids)
                for key, value in vars(obj).items()
            }
        return obj
    finally:
        active_object_ids.remove(object_id)


def main() -> None:
    """Load parser inputs, dispatch parsing, and write binary and text results."""
    parser = argparse.ArgumentParser(description="Run load dispatch parser")
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to manifest JSON file containing classified input file lists",
    )
    parser.add_argument(
        "--franca-files",
        nargs="*",
        default=[],
        help="List of Franca source files (.fidl, .fdepl)",
    )
    parser.add_argument(
        "--protobuf-files",
        nargs="*",
        default=[],
        help="List of Protobuf descriptor set files (.bin, .desc, .pb)",
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
        required=True,
        help="Path to human-readable text output file",
    )
    args, _ = parser.parse_known_args()

    if args.manifest:
        manifest_path = Path(args.manifest)
        with manifest_path.open("r", encoding="utf-8") as manifest_file:
            manifest_data = json.load(manifest_file)
        parser_input_files = {
            "franca_files": manifest_data.get("franca_files", []),
            "protobuf_files": manifest_data.get("protobuf_files", []),
        }
    else:
        parser_input_files = {
            "franca_files": args.franca_files,
            "protobuf_files": args.protobuf_files,
        }

    output_dump_path = Path(args.output)
    text_dump_path = Path(args.text_output)
    if "BUILD_WORKSPACE_DIRECTORY" in os.environ:
        workspace_directory = Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])
        if not output_dump_path.is_absolute():
            output_dump_path = workspace_directory / output_dump_path
        if not text_dump_path.is_absolute():
            text_dump_path = workspace_directory / text_dump_path

    output_dump_path.parent.mkdir(parents=True, exist_ok=True)
    text_dump_path.parent.mkdir(parents=True, exist_ok=True)

    result = load_and_parse(
        franca_files_desc = ParsingPathInfo(src_files=tuple(parser_input_files["franca_files"])),
        protobuf_files_desc = ParsingPathInfo(src_files=tuple(parser_input_files["protobuf_files"])),
        return_parsed_object = True,
    )

    with output_dump_path.open("wb") as output_file:
        output_file.write(result)

    # Keep the text dump available for debugging when human-readable output is needed.
    text_dump_path.write_text(
        json.dumps(_stringify_keys(pickle.loads(result)), indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )

    # TBD: resolver, entrance is the selected submodule {datatype, interface, ...} etc

    # pickle dump

if __name__ == "__main__":
    main()
