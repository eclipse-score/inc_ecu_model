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

from os import getpid

from score.parsers.protobuf_parser.api import ProtobufToDataTypeParser
from score.parsers.runner.common import Parser


class WrapperProtobufParser(Parser):
    def __init__(self, path_info):
        """Adapter for Protobuf parser."""
        super().__init__(path_info)
        self.protobuf_files = path_info.src_files

    def parse(self) -> dict[str, object]:
        """Parse protobuf descriptor files and return the definitions mapping."""

        if not self.protobuf_files:
            result: dict[str, object] = {"data_types": {}}
            return result

        registry = ProtobufToDataTypeParser.parse(self.protobuf_files)

        result = {"data_types": registry}

        return result
