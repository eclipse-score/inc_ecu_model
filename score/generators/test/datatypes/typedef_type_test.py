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

"""Verify typedef targets, usage includes and rendering."""

import tempfile
import unittest
from pathlib import Path

from score.ecu_model.data_types.common import DataTypeSource
from score.ecu_model.data_types.enum import EnumDataType, EnumValue
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.model import ModelRegistry
from score.generators.src.datatypes.cpp_model import CppAlias
from score.generators.src.datatypes.datatype_generator import DatatypeGenerator
from score.generators.src.datatypes.datatype_utils import DatatypeUtils


class TypedefTypeTest(unittest.TestCase):
    """Verify typedef targets, usage includes and rendering."""

    def setUp(self):
        """Isolate model objects registered during each test."""
        ModelRegistry.elements.clear()
        self.addCleanup(ModelRegistry.elements.clear)

    def test_typedef_struct_target_emits_its_dependency_first(self):
        """Aliases reuse a completed struct's name and usage include."""
        record = StructDataType(name="Record", source_kind=DataTypeSource.FRANCA, fields=[])
        alias = TypedefDataType(name="Alias", source_kind=DataTypeSource.FRANCA, data_type=record)
        headers = []

        DatatypeUtils.build_type_registry([alias], headers.append)

        self.assertEqual([header.path for header in headers], ["Record.h", "Alias.h"])
        self.assertEqual(headers[-1].declaration, CppAlias("Alias", "::Record"))
        self.assertEqual(headers[-1].includes, ("Record.h",))

    def test_generator_emits_typedef_headers_without_mutating_inputs(self):
        """A final-model section flows through collection, lowering, and rendering."""
        alias = TypedefDataType(
            name="Count",
            namespace="example",
            source_kind=DataTypeSource.FRANCA,
            data_type=PrimitiveDataType.UINT16,
        )
        original_model = alias.model_dump()
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "out"
            DatatypeGenerator().generate({"data_types": {alias.id: alias}}, output_dir)
            content = (output_dir / "example/Count.h").read_text(encoding="utf-8")
            self.assertIn("#include <cstdint>", content)
            self.assertIn("using Count = std::uint16_t;", content)
            self.assertIn("namespace example {", content)
            self.assertEqual(alias.model_dump(), original_model)

    def test_selected_enum_typedef_generates_its_target_before_the_alias(self):
        """An alias discovers and shares its enum dependency without separately selecting it."""
        enumeration = EnumDataType(
            name="Mode",
            namespace="shared",
            source_kind=DataTypeSource.FRANCA,
            values=(EnumValue(name="Idle", value=0),),
        )
        alias = TypedefDataType(name="ModeAlias", source_kind=DataTypeSource.FRANCA, data_type=enumeration)
        headers = []

        DatatypeUtils.build_type_registry([alias, enumeration, alias], headers.append)

        self.assertEqual([header.path for header in headers], ["shared/Mode.h", "ModeAlias.h"])
        self.assertEqual(headers[1].declaration, CppAlias("ModeAlias", "::shared::Mode"))
        self.assertEqual(headers[1].includes, ("shared/Mode.h",))


if __name__ == "__main__":
    unittest.main()
