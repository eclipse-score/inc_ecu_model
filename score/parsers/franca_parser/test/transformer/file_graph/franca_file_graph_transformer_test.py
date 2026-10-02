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

"""Behavior tests for Franca file graph transformation."""

import unittest
from pathlib import Path

from score.parsers.franca_parser.parser import FrancaParser
from score.parsers.franca_parser.transformer.file_graph_transformer import (
    FrancaFileGraphTransformer,
)

TEST_DATA_DIRECTORY = Path(__file__).parents[5] / "test_data/franca/file_graph"


class FrancaFileGraphTransformerTest(unittest.TestCase):
    """Verify import-first traversal and import-cycle completion."""

    def test_transform_files_given_direct_import_expect_import_stored_before_importer(self) -> None:
        root_file = TEST_DATA_DIRECTORY / "root_imports_types.fidl"
        imported_file = TEST_DATA_DIRECTORY / "imported_types.fidl"
        parser = FrancaParser(root_files=[root_file], dependency_files=[imported_file])

        transformed_files = FrancaFileGraphTransformer(parser.parse_files()).transform_files()

        self.assertEqual(
            list(transformed_files),
            [imported_file.resolve(), root_file.resolve()],
        )
        self.assertEqual(
            transformed_files[root_file.resolve()].namespace.as_str,
            "example.franca.root",
        )

    def test_transform_files_given_import_cycle_expect_each_file_transformed_once(self) -> None:
        left_file = TEST_DATA_DIRECTORY / "left_cycle.fidl"
        right_file = TEST_DATA_DIRECTORY / "right_cycle.fidl"
        parser = FrancaParser(root_files=[left_file], dependency_files=[right_file])

        transformed_files = FrancaFileGraphTransformer(parser.parse_files()).transform_files()

        self.assertEqual(set(transformed_files), {left_file.resolve(), right_file.resolve()})


if __name__ == "__main__":
    unittest.main()
