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

"""Command-line entry point for merging parser registry outputs."""

from __future__ import annotations

import argparse
import json
import os
import pickle
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from score.parsers.runner.load_and_merge import load_and_merge


def _stringify_keys(value: Any, active_object_ids: set[int] | None = None) -> Any:
    """Convert model objects to JSON-friendly values while marking cycles."""
    if active_object_ids is None:
        active_object_ids = set()

    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    object_id = id(value)
    if object_id in active_object_ids:
        return "..."
    active_object_ids.add(object_id)

    try:
        if isinstance(value, dict):
            return {str(key): _stringify_keys(item, active_object_ids) for key, item in value.items()}
        if isinstance(value, (list, tuple, set, frozenset)):
            return [_stringify_keys(item, active_object_ids) for item in value]
        if is_dataclass(value) and not isinstance(value, type):
            return {
                field.name: _stringify_keys(getattr(value, field.name), active_object_ids) for field in fields(value)
            }
        if isinstance(value, BaseModel):
            return {
                field_name: _stringify_keys(getattr(value, field_name), active_object_ids)
                for field_name in type(value).model_fields
            }
        if hasattr(value, "__dict__"):
            return {str(key): _stringify_keys(item, active_object_ids) for key, item in vars(value).items()}
        return value
    finally:
        active_object_ids.remove(object_id)


def main() -> None:
    """Merge raw parser registries and write the final result as pickle and optional JSON."""
    argument_parser = argparse.ArgumentParser(description="Load and merge parser outputs")
    argument_parser.add_argument("--registry-pickle", action="append", default=[])
    argument_parser.add_argument("--output", required=True)
    argument_parser.add_argument("--text-output")
    arguments = argument_parser.parse_args()

    output_path = Path(arguments.output)
    text_output_path = Path(arguments.text_output) if arguments.text_output else None
    workspace_directory = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if workspace_directory:
        workspace = Path(workspace_directory)
        if not output_path.is_absolute():
            output_path = workspace / output_path
        if text_output_path is not None and not text_output_path.is_absolute():
            text_output_path = workspace / text_output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if text_output_path is not None:
        text_output_path.parent.mkdir(parents=True, exist_ok=True)

    result = load_and_merge(arguments.registry_pickle)
    output_path.write_bytes(pickle.dumps(result, protocol=pickle.HIGHEST_PROTOCOL))

    if text_output_path is not None:
        text_output_path.write_text(
            json.dumps(_stringify_keys(result), indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
