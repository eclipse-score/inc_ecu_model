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

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields, is_dataclass
import json
from pathlib import Path
from typing import Any, Union

from pydantic import BaseModel

from score.ecu_model.model import ModelRegistry

PathEntry = Union[str, Path]


@dataclass
class ParsingPathInfo:
    src_files: tuple[str, ...]
    """Paths to the source files to be parsed."""

    parsed_model_files: tuple[str, ...] | None = None
    """Paths to the parsed model files. See the README.md for more details."""

    result_pickle_path: str | None = None
    """Path to the pickle file where the parser result will be stored. See the README.md for more details."""

    ext_info: dict = field(default_factory=dict)
    """Additional external information that might be needed by the parser."""


def _stringify_keys(obj: Any, active_object_ids: set[int] | None = None) -> Any:
    """Convert nested model values into JSON-friendly structures and mark cycles."""
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


def write_parser_outputs(
    path_info: ParsingPathInfo,
) -> None:
    """Write the serialized model registry when an output path is configured."""
    if path_info.result_pickle_path is None:
        return

    registry_path = Path(path_info.result_pickle_path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_bytes(ModelRegistry.serialize())


class Parser(ABC):
    """Base interface for parser implementations."""

    def __init__(self, path_info: ParsingPathInfo) -> None:
        """Base interface for parser implementations.

        :param path_info: Source, output, and parser-specific path information.
        """
        super().__init__()
        self.path_info = path_info

    @abstractmethod
    def parse(self):
        """Parse the configured source files.
        """
        pass
