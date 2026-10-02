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

"""Behavior tests for FIDL parsing and import discovery."""

import unittest
from pathlib import Path

from score.parsers.franca_parser.parser import FrancaParser

TEST_DATA_DIRECTORY = Path(__file__).parent / "test_data"
SHARED_IMPORT_DIRECTORY = Path(__file__).parents[4] / "test_data/franca/shared_import"


class FrancaParserTest(unittest.TestCase):
    """Verify parsing and import-discovery behavior."""

    def test_parse_files_given_transitive_imports_expect_each_file_parsed_once(self) -> None:
        parser = FrancaParser(
            root_files=[
                SHARED_IMPORT_DIRECTORY / "first_root_imports_shared.fidl",
                SHARED_IMPORT_DIRECTORY / "second_root_imports_shared.fidl",
            ],
            dependency_files=[SHARED_IMPORT_DIRECTORY / "shared_types.fidl"],
        )

        parsed_files = parser.parse_files()

        self.assertEqual(len(parsed_files), 3)
        self.assertEqual(
            parsed_files[(SHARED_IMPORT_DIRECTORY / "shared_types.fidl").resolve()].imports,
            [],
        )

    def test_parse_files_given_missing_declared_import_expect_contextual_error(self) -> None:
        missing_import_file = TEST_DATA_DIRECTORY / "missing_import.fidl"
        parser = FrancaParser(root_files=[missing_import_file], dependency_files=[])

        with self.assertRaisesRegex(FileNotFoundError, "missing_types.fidl.*missing_import.fidl"):
            parser.parse_files()


if __name__ == "__main__":
    unittest.main()
