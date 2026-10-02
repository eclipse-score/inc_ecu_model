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

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from score.ecu_model.model import ModelRegistry
from score.ecu_model.query import datatypes_by_name
from score.orchestrator.run_parser import main
from score.test_data.inputs import write_descriptor_set, write_fidl


class RunParserTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_registry = dict(ModelRegistry.elements)
        ModelRegistry.elements.clear()
        self._temp_dir = TemporaryDirectory()
        self._directory = Path(self._temp_dir.name)
        self._output = self._directory / "partial.pkl"

    def tearDown(self) -> None:
        self._temp_dir.cleanup()
        ModelRegistry.elements.clear()
        ModelRegistry.elements.update(self._saved_registry)

    def _load_output(self) -> set[str]:
        ModelRegistry.deserialize(self._output.read_bytes())
        return set(datatypes_by_name())

    def test_main_given_franca_parser_expect_partial_model_with_franca_datatypes(self) -> None:
        fidl = write_fidl(self._directory, "example.franca", "Types", "Value")

        main(["--parser", "franca", "--src", str(fidl), "--output", str(self._output)])

        self.assertEqual(self._load_output(), {"example.franca.Types.Value"})

    def test_main_given_protobuf_parser_with_dependency_expect_both_datatypes(self) -> None:
        src = write_descriptor_set(self._directory, "example.proto", "Root")
        dependency = write_descriptor_set(self._directory, "example.proto", "Dependency")

        main(["--parser", "protobuf", "--src", str(src), "--dep", str(dependency), "--output", str(self._output)])

        self.assertEqual(self._load_output(), {"example.proto.Root", "example.proto.Dependency"})

    def test_main_given_missing_input_expect_error_and_no_output(self) -> None:
        missing_fidl = self._directory / "missing.fidl"

        with self.assertRaises(FileNotFoundError):
            main(["--parser", "franca", "--src", str(missing_fidl), "--output", str(self._output)])

        self.assertFalse(self._output.exists())

    def test_main_given_unknown_parser_expect_usage_error(self) -> None:
        with self.assertRaises(SystemExit):
            main(["--parser", "unknown", "--src", "a.idl", "--output", str(self._output)])

    def test_main_given_info_level_expect_start_and_finish_logged(self) -> None:
        fidl = write_fidl(self._directory, "example.franca", "Types", "Value")

        with self.assertLogs("score.orchestrator", level="INFO") as logs:
            main(["--parser", "franca", "--src", str(fidl), "--output", str(self._output)])

        self.assertEqual(len(logs.output), 2)
        self.assertIn("Starting franca parser with 1 source file(s) and 0 dependency file(s)", logs.output[0])
        self.assertRegex(logs.output[1], r"franca parser finished after \d+\.\d{2} s, created \d+ model element\(s\)")


if __name__ == "__main__":
    unittest.main()
