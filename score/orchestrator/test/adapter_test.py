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

from score.ecu_model.data_types.struct import StructDataType
from score.orchestrator.common import ParsingPathInfo
from score.orchestrator.franca_adapter import FrancaAdapter
from score.orchestrator.protobuf_adapter import ProtobufAdapter
from score.orchestrator.test.inputs import write_descriptor_set, write_fidl


class FrancaAdapterTest(unittest.TestCase):
    def test_parse_given_fidl_file_expect_struct_by_fqn(self) -> None:
        with TemporaryDirectory() as directory:
            fidl = write_fidl(Path(directory), "example.franca", "Types", "Value")

            datatypes = FrancaAdapter(ParsingPathInfo(src_files=(fidl,))).parse()

        self.assertEqual(list(datatypes), ["example.franca.Types.Value"])
        self.assertIsInstance(datatypes["example.franca.Types.Value"], StructDataType)


class ProtobufAdapterTest(unittest.TestCase):
    def test_parse_given_descriptor_set_expect_struct_by_fqn(self) -> None:
        with TemporaryDirectory() as directory:
            descriptor_set = write_descriptor_set(Path(directory), "example.proto", "Value")

            datatypes = ProtobufAdapter(ParsingPathInfo(src_files=(descriptor_set,))).parse()

        self.assertEqual(list(datatypes), ["example.proto.Value"])
        self.assertIsInstance(datatypes["example.proto.Value"], StructDataType)

    def test_parse_given_dependency_descriptor_set_expect_its_datatypes_included(self) -> None:
        with TemporaryDirectory() as directory:
            src = write_descriptor_set(Path(directory), "example.proto", "Root")
            dependency = write_descriptor_set(Path(directory), "example.proto", "Dependency")

            datatypes = ProtobufAdapter(ParsingPathInfo(src_files=(src,), dependency_files=(dependency,))).parse()

        self.assertEqual(set(datatypes), {"example.proto.Root", "example.proto.Dependency"})


if __name__ == "__main__":
    unittest.main()
