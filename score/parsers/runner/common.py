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
from pathlib import Path
from typing import Union
from dataclasses import dataclass, field

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


class Parser(ABC):
    def __init__(self, path_info: ParsingPathInfo) -> None:
        super().__init__()
        self.path_info = path_info

    @abstractmethod
    def parse(self) -> dict[str, object]:
        """Parse the source files and returns the parsed model as a dictionary."""
        pass
