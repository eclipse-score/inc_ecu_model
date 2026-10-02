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

import logging
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from score.ecu_model.model import ModelRegistry
from score.ecu_model.query import datatypes_by_name
from score.orchestrator.common import ParsingPathInfo
from score.orchestrator.load_dispatch import _ForwardToLocalLogger, load_and_parse
from score.test_data.inputs import write_descriptor_set, write_fidl


def registered_datatype_names() -> set[str]:
    return set(datatypes_by_name())


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

    def test_load_and_parse_given_franca_and_protobuf_expect_both_datatypes_registered(self) -> None:
        fidl = write_fidl(self._directory, "example.franca", "Types", "Value")
        descriptor_set = write_descriptor_set(self._directory, "example.proto", "Value")

        load_and_parse(
            franca=ParsingPathInfo(src_files=(fidl,)),
            protobuf=ParsingPathInfo(src_files=(descriptor_set,)),
        )

        self.assertEqual(registered_datatype_names(), {"example.franca.Types.Value", "example.proto.Value"})

    def test_load_and_parse_given_only_franca_expect_franca_datatypes_registered(self) -> None:
        fidl = write_fidl(self._directory, "example.franca", "Types", "Value")

        load_and_parse(franca=ParsingPathInfo(src_files=(fidl,)))

        self.assertEqual(registered_datatype_names(), {"example.franca.Types.Value"})

    def test_load_and_parse_given_only_protobuf_expect_protobuf_datatypes_registered(self) -> None:
        descriptor_set = write_descriptor_set(self._directory, "example.proto", "Value")

        load_and_parse(protobuf=ParsingPathInfo(src_files=(descriptor_set,)))

        self.assertEqual(registered_datatype_names(), {"example.proto.Value"})

    def test_load_and_parse_given_no_inputs_expect_registry_unchanged(self) -> None:
        load_and_parse()

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

    def test_load_and_parse_given_parsed_datatypes_expect_field_references_resolve_within_registry(self) -> None:
        write_fidl(self._directory, "example.franca", "Types", "Value")
        fidl = self._directory / "Root.fidl"
        fidl.write_text(
            "package example.root\n"
            'import example.franca.* from "Value.fidl"\n'
            "typeCollection RootTypes {\n"
            "    struct Root {\n"
            "        Types.Value value\n"
            "    }\n"
            "}\n"
        )

        load_and_parse(
            franca=ParsingPathInfo(src_files=(fidl,), dependency_files=(self._directory / "Value.fidl",)),
        )

        datatypes = datatypes_by_name()
        root = datatypes["example.root.RootTypes.Root"]
        value = datatypes["example.franca.Types.Value"]
        self.assertIs(root.fields[0].data_type, value)
        self.assertIs(ModelRegistry.elements[value.id], value)

    def test_load_and_parse_given_only_franca_expect_child_logs_forwarded_before_merge_log(self) -> None:
        fidl = write_fidl(self._directory, "example.franca", "Types", "Value")

        with self.assertLogs("score.orchestrator", level="INFO") as logs:
            load_and_parse(franca=ParsingPathInfo(src_files=(fidl,)))

        self.assertEqual(len(logs.output), 3)
        self.assertIn("Starting franca parser with 1 source file(s) and 0 dependency file(s)", logs.output[0])
        self.assertRegex(logs.output[1], r"franca parser finished after \d+\.\d{2} s, created \d+ model element\(s\)")
        self.assertRegex(logs.output[2], r"Merged \d+ model element\(s\) of 1 parser\(s\) in \d+\.\d{2} s")

    def test_load_and_parse_given_info_level_expect_debug_records_not_transferred(self) -> None:
        fidl = write_fidl(self._directory, "example.franca", "Types", "Value")
        forwarded_levels: list[int] = []
        original_emit = _ForwardToLocalLogger.emit

        def capture_level(handler: _ForwardToLocalLogger, record: logging.LogRecord) -> None:
            forwarded_levels.append(record.levelno)
            original_emit(handler, record)

        with (
            patch.object(_ForwardToLocalLogger, "emit", capture_level),
            self.assertLogs("score.orchestrator", level="INFO"),
        ):
            load_and_parse(franca=ParsingPathInfo(src_files=(fidl,)))

        self.assertEqual(forwarded_levels, [logging.INFO, logging.INFO])

    def test_load_and_parse_given_debug_level_expect_child_input_files_logged(self) -> None:
        fidl = write_fidl(self._directory, "example.franca", "Types", "Value")

        with self.assertLogs("score.orchestrator", level="DEBUG") as logs:
            load_and_parse(franca=ParsingPathInfo(src_files=(fidl,)))

        self.assertTrue(any(f"franca parser input files: {fidl}" in message for message in logs.output))


if __name__ == "__main__":
    unittest.main()
