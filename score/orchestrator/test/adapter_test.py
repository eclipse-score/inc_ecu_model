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
from score.ecu_model.model import ModelRegistry
from score.ecu_model.query import datatypes_by_name
from score.orchestrator.common import ParsingPathInfo
from score.orchestrator.franca_adapter import FrancaAdapter
from score.orchestrator.protobuf_adapter import ProtobufAdapter
from score.orchestrator.test.inputs import write_descriptor_set, write_fidl


class _RegistryIsolation(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_registry = dict(ModelRegistry.elements)
        ModelRegistry.elements.clear()

    def tearDown(self) -> None:
        ModelRegistry.elements.clear()
        ModelRegistry.elements.update(self._saved_registry)


class FrancaAdapterTest(_RegistryIsolation):
    def test_parse_given_fidl_file_expect_struct_registered(self) -> None:
        with TemporaryDirectory() as directory:
            fidl = write_fidl(Path(directory), "example.franca", "Types", "Value")

            FrancaAdapter(ParsingPathInfo(src_files=(fidl,))).parse()

        datatypes = datatypes_by_name()
        self.assertEqual(list(datatypes), ["example.franca.Types.Value"])
        self.assertIsInstance(datatypes["example.franca.Types.Value"], StructDataType)


class ProtobufAdapterTest(_RegistryIsolation):
    def test_parse_given_descriptor_set_expect_struct_registered(self) -> None:
        with TemporaryDirectory() as directory:
            descriptor_set = write_descriptor_set(Path(directory), "example.proto", "Value")

            ProtobufAdapter(ParsingPathInfo(src_files=(descriptor_set,))).parse()

        datatypes = datatypes_by_name()
        self.assertEqual(list(datatypes), ["example.proto.Value"])
        self.assertIsInstance(datatypes["example.proto.Value"], StructDataType)

    def test_parse_given_dependency_descriptor_set_expect_its_datatypes_registered(self) -> None:
        with TemporaryDirectory() as directory:
            src = write_descriptor_set(Path(directory), "example.proto", "Root")
            dependency = write_descriptor_set(Path(directory), "example.proto", "Dependency")

            ProtobufAdapter(ParsingPathInfo(src_files=(src,), dependency_files=(dependency,))).parse()

        self.assertEqual(set(datatypes_by_name()), {"example.proto.Root", "example.proto.Dependency"})


if __name__ == "__main__":
    unittest.main()
