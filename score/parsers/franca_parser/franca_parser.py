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
from pathlib import Path

from score.parsers.franca_parser.model.fidl.fidl_file import FIDLFileModel
from score.parsers.franca_parser.parser import FrancaParser
from score.parsers.franca_parser.transformer.file_graph_transformer import (
    FrancaFileGraphTransformer,
)
from score.parsers.runner.common import Parser


class WrapperFrancaParser(Parser):
    def __init__(self, path_info):
        """Adapter for Franca parser."""
        super().__init__(path_info)

        self.franca_files = path_info.src_files
        self.dependency_files = path_info.ext_info.get("dependency_files", ())
        self.defined = path_info.ext_info.get("defined")
        self.need_preprocessor = path_info.ext_info.get("need_preprocessor", False)

    def parse(self) -> dict[str, object]:
        """Parse Franca files and return the transformed file models."""

        if not self.franca_files:
            parser_pid = getpid()
            result: dict[str, object] = {"data_types": {}}
            return result

        root_paths = [Path(file_path) for file_path in self.franca_files]
        dep_paths = [Path(file_path) for file_path in self.dependency_files]

        franca_parser = FrancaParser(
            root_files=root_paths,
            dependency_files=dep_paths,
            defined=self.defined,
            need_preprocessor=self.need_preprocessor,
        )
        parsed_files = franca_parser.parse_files()
        transformed_files = FrancaFileGraphTransformer(parsed_files).transform_files()
        datatypes = {}
        for file_model in transformed_files.values():
            if isinstance(file_model, FIDLFileModel):
                datatypes.update(file_model._datatype_index)

        result = {"data_types": datatypes}

        return result
