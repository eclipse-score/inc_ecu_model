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
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from score.parsers.franca_parser.parser import FrancaParser

TEST_DATA_DIRECTORY = Path(__file__).parent / "test_data"


class FrancaParserTest(unittest.TestCase):
    """Verify parsing and import-discovery behavior."""

    def test_parse_files_given_transitive_imports_expect_each_file_parsed_once(self) -> None:
        parser = FrancaParser(
            root_files=[
                TEST_DATA_DIRECTORY / "first_root_imports_shared.fidl",
                TEST_DATA_DIRECTORY / "second_root_imports_shared.fidl",
            ],
            dependency_files=[TEST_DATA_DIRECTORY / "shared_types.fidl"],
        )

        parsed_files = parser.parse_files()

        self.assertEqual(len(parsed_files), 3)
        self.assertEqual(
            parsed_files[(TEST_DATA_DIRECTORY / "shared_types.fidl").resolve()].imports,
            [],
        )

    def test_parse_files_given_missing_declared_import_expect_contextual_error(self) -> None:
        missing_import_file = TEST_DATA_DIRECTORY / "missing_import.fidl"
        parser = FrancaParser(root_files=[missing_import_file], dependency_files=[])

        with self.assertRaisesRegex(FileNotFoundError, "missing_types.fidl.*missing_import.fidl"):
            parser.parse_files()

    def test_preprocess_files_when_preprocessor_not_needed_reads_original_content(self) -> None:
        content = "#if defined(FEATURE)\nkept\n#else\nexcluded\n#endif\n"
        parser = FrancaParser(root_files=[], dependency_files=[])

        with TemporaryDirectory() as temp_directory:
            file_path = Path(temp_directory) / "condition.fidl"
            file_path.write_text(content, encoding="utf-8")

            result = parser._preprocess_files([file_path], ["FEATURE"], False)

        self.assertEqual(result, {str(file_path.resolve()): content})

    def test_preprocess_files_when_preprocessor_needed_uses_batch_runner(self) -> None:
        parser = FrancaParser(root_files=[], dependency_files=[])
        expected = {"condition.fidl": "processed content"}

        with patch("score.parsers.franca_parser.parser.BatchRunner") as batch_runner_type:
            batch_runner_type.return_value.batch_run.return_value = expected

            result = parser._preprocess_files([Path("condition.fidl")], ["FEATURE"], True)

        batch_runner_type.assert_called_once_with(
            file_list=[Path("condition.fidl")],
            defined_list=["FEATURE"],
        )
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
