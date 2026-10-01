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

"""Common interface of the parsers run by the orchestrator."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
from pathlib import Path
import time
from typing import ClassVar

from score.ecu_model.data_types.common import DataTypeBase
from score.ecu_model.model import ModelRegistry

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsingPathInfo:
    """
    Input files of one parser.

    Attributes:
        src_files: Root files to parse, e.g. FIDL/FDEPL files or protoc descriptor sets.
        dependency_files: Files the root files may import. The Franca parser only parses those reachable via imports,
            the Protobuf parser parses all of them together with src_files.
    """

    src_files: tuple[Path, ...] = ()
    dependency_files: tuple[Path, ...] = ()


class Parser(ABC):
    """
    Adapter between the orchestrator and one IDL parser.

    Attributes:
        name: Short parser name used in logs and error messages.
    """

    name: ClassVar[str]

    def __init__(self, path_info: ParsingPathInfo) -> None:
        self._path_info = path_info

    def run(self) -> dict[str, DataTypeBase]:
        """Call parse() and log its inputs, its duration and the number of model elements it created."""
        _logger.info(
            "Starting %s parser with %d source file(s) and %d dependency file(s)",
            self.name,
            len(self._path_info.src_files),
            len(self._path_info.dependency_files),
        )
        _logger.debug(
            "%s parser input files: %s",
            self.name,
            ", ".join(str(path) for path in self._path_info.src_files + self._path_info.dependency_files),
        )
        elements_before = len(ModelRegistry.elements)
        start = time.perf_counter()
        result = self.parse()
        _logger.info(
            "%s parser finished after %.2f s, created %d model element(s)",
            self.name,
            time.perf_counter() - start,
            len(ModelRegistry.elements) - elements_before,
        )
        return result

    @abstractmethod
    def parse(self) -> dict[str, DataTypeBase]:
        """Parse the input files and return the datatypes by fully qualified name."""
