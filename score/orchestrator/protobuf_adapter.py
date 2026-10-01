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

"""Orchestrator adapter for the Protobuf parser."""

from __future__ import annotations

from score.ecu_model.data_types.common import DataTypeBase
from score.orchestrator.common import Parser
from score.parsers.protobuf_parser.api import ProtobufToDataTypeParser


class ProtobufAdapter(Parser):
    """Parse protoc descriptor sets and return their datatypes."""

    name = "protobuf"

    def parse(self) -> dict[str, DataTypeBase]:
        """Parse the descriptor sets and return the datatypes by fully qualified name."""
        return ProtobufToDataTypeParser.parse(self._path_info.src_files + self._path_info.dependency_files)
