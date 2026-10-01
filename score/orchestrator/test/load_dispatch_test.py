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

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from score.ecu_model.model import ModelRegistry
from score.orchestrator.common import ParsingPathInfo
from score.orchestrator.load_dispatch import load_and_parse
from score.orchestrator.test.inputs import write_descriptor_set, write_fidl


class LoadAndParseTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_registry = dict(ModelRegistry.elements)
        ModelRegistry.elements.clear()
        self._temp_dir = TemporaryDirectory()
        self._directory = Path(self._temp_dir.name)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()
        ModelRegistry.elements.clear()
        ModelRegistry.elements.update(self._saved_registry)

    def test_load_and_parse_given_franca_and_protobuf_expect_merged_datatypes(self) -> None:
        fidl = write_fidl(self._directory, "example.franca", "Types", "Value")
        descriptor_set = write_descriptor_set(self._directory, "example.proto", "Value")

        datatypes = load_and_parse(
            franca=ParsingPathInfo(src_files=(fidl,)),
            protobuf=ParsingPathInfo(src_files=(descriptor_set,)),
        )

        self.assertEqual(set(datatypes), {"example.franca.Types.Value", "example.proto.Value"})

    def test_load_and_parse_given_only_franca_expect_franca_datatypes(self) -> None:
        fidl = write_fidl(self._directory, "example.franca", "Types", "Value")

        datatypes = load_and_parse(franca=ParsingPathInfo(src_files=(fidl,)))

        self.assertEqual(set(datatypes), {"example.franca.Types.Value"})

    def test_load_and_parse_given_only_protobuf_expect_protobuf_datatypes(self) -> None:
        descriptor_set = write_descriptor_set(self._directory, "example.proto", "Value")

        datatypes = load_and_parse(protobuf=ParsingPathInfo(src_files=(descriptor_set,)))

        self.assertEqual(set(datatypes), {"example.proto.Value"})

    def test_load_and_parse_given_no_inputs_expect_empty_result(self) -> None:
        self.assertEqual(load_and_parse(), {})
        self.assertEqual(ModelRegistry.elements, {})

    def test_load_and_parse_given_failing_parser_expect_runtime_error_naming_it(self) -> None:
        descriptor_set = write_descriptor_set(self._directory, "example.proto", "Value")
        missing_fidl = self._directory / "missing.fidl"

        with self.assertRaisesRegex(RuntimeError, "franca: FileNotFoundError"):
            load_and_parse(
                franca=ParsingPathInfo(src_files=(missing_fidl,)),
                protobuf=ParsingPathInfo(src_files=(descriptor_set,)),
            )
        self.assertEqual(ModelRegistry.elements, {})

    def test_load_and_parse_given_same_fqn_in_both_parsers_expect_value_error(self) -> None:
        fidl = write_fidl(self._directory, "example.shared", "Types", "Value")
        descriptor_set = write_descriptor_set(self._directory, "example.shared.Types", "Value")

        with self.assertRaisesRegex(ValueError, "example.shared.Types.Value"):
            load_and_parse(
                franca=ParsingPathInfo(src_files=(fidl,)),
                protobuf=ParsingPathInfo(src_files=(descriptor_set,)),
            )
        self.assertEqual(ModelRegistry.elements, {})

    def test_load_and_parse_given_parsed_datatypes_expect_them_registered_in_main_process(self) -> None:
        fidl = write_fidl(self._directory, "example.franca", "Types", "Value")
        descriptor_set = write_descriptor_set(self._directory, "example.proto", "Value")

        datatypes = load_and_parse(
            franca=ParsingPathInfo(src_files=(fidl,)),
            protobuf=ParsingPathInfo(src_files=(descriptor_set,)),
        )

        for datatype in datatypes.values():
            self.assertIs(ModelRegistry.elements[datatype.id], datatype)

    def test_load_and_parse_given_only_franca_expect_child_logs_forwarded_before_merge_log(self) -> None:
        fidl = write_fidl(self._directory, "example.franca", "Types", "Value")

        with self.assertLogs("score.orchestrator", level="INFO") as logs:
            load_and_parse(franca=ParsingPathInfo(src_files=(fidl,)))

        self.assertEqual(len(logs.output), 3)
        self.assertIn("Starting franca parser with 1 source file(s) and 0 dependency file(s)", logs.output[0])
        self.assertRegex(logs.output[1], r"franca parser finished after \d+\.\d{2} s, created \d+ model element\(s\)")
        self.assertRegex(logs.output[2], r"Merged results of 1 parser\(s\) in \d+\.\d{2} s")


if __name__ == "__main__":
    unittest.main()
