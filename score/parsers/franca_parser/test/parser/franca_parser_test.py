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
from tempfile import TemporaryDirectory
from unittest.mock import patch

import score.parsers.franca_parser as franca_parser
from score.parsers.franca_parser.parser import FrancaParser
from score.parsers.franca_parser.transformer.file_graph_transformer import FrancaFileGraphTransformer

TEST_DATA_DIRECTORY = Path(__file__).parent / "test_data"


class FrancaParserTest(unittest.TestCase):
    """Verify parsing and import-discovery behavior."""

    def test_package_exports_public_parser_api(self) -> None:
        self.assertIs(franca_parser.FrancaParser, FrancaParser)
        self.assertIs(franca_parser.FrancaFileGraphTransformer, FrancaFileGraphTransformer)
        self.assertEqual(franca_parser.__all__, ["FrancaFileGraphTransformer", "FrancaParser"])

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

    def test_general_deployments_preserve_type_collection_and_interface(self) -> None:
        with TemporaryDirectory() as temp_directory:
            directory = Path(temp_directory)
            design_file = directory / "service.fidl"
            design_file.write_text(
                "package demo\n"
                "typeCollection Types { struct Payload { UInt32 value } }\n"
                "interface API { version { major 1 minor 0 } method ping {} }\n",
                encoding="utf-8",
            )
            for suffix in (".fdepl", ".cdepl"):
                with self.subTest(suffix=suffix):
                    deployment_file = directory / f"deployment{suffix}"
                    deployment_file.write_text(
                        'package demo.deployment\nimport "service.fidl"\n'
                        "specification example { for interfaces { Marker: Integer (optional); } }\n"
                        "define example for typeCollection demo.Types as TypesDeployment {\n"
                        "    CollectionMarker = 42 struct Payload {}\n"
                        "}\n"
                        "define example for interface demo.API major 1 as ApiDeployment {\n"
                        "    Marker = 7 method ping {}\n"
                        "}\n",
                        encoding="utf-8",
                    )
                    parser = FrancaParser(root_files=[deployment_file], dependency_files=[design_file])
                    parsed_files = parser.parse_files()
                    parse_tree = parsed_files[deployment_file.resolve()].parse_tree
                    self.assertEqual(len(list(parse_tree.find_data("fd_general"))), 2)

                    transformer = FrancaFileGraphTransformer(parsed_files)
                    transformer.transform_files()
                    model = transformer.transformed_files[deployment_file.resolve()]
                    collection = model.type_collection_deployments[0]
                    interface = model.interface_deployments[0]
                    self.assertEqual(collection.specification.name.as_str, "example")
                    self.assertEqual(collection.target.name.as_str, "Types")
                    self.assertEqual(collection.name.as_str, "TypesDeployment")
                    self.assertEqual(collection.parameter_set[0].value, 42)
                    self.assertEqual(collection.deployment_elements[0].deployed_type.name.as_str, "Payload")
                    self.assertEqual(interface.specification.name.as_str, "example")
                    self.assertEqual(interface.target.name.as_str, "API")
                    self.assertEqual(interface.name.as_str, "ApiDeployment")
                    self.assertEqual(interface.version.major, 1)
                    self.assertEqual(interface.parameter_set[0].value, 7)
                    self.assertEqual(interface.deployment_elements[0].deployed_type.name.as_str, "ping")

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
