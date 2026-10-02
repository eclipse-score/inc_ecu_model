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

"""Orchestrator adapter for the Franca parser."""

from __future__ import annotations

from score.parsers.franca_parser.parser import FrancaParser
from score.parsers.franca_parser.transformer.file_graph_transformer import (
    FrancaFileGraphTransformer,
)
from score.orchestrator.common import Parser


class FrancaAdapter(Parser):
    """Parse FIDL and FDEPL files into ModelRegistry."""

    name = "franca"

    def parse(self) -> None:
        """Parse and transform the Franca files, which creates their model elements."""
        parser = FrancaParser(
            root_files=list(self._path_info.src_files),
            dependency_files=list(self._path_info.dependency_files),
        )
        FrancaFileGraphTransformer(parser.parse_files()).transform_files()
