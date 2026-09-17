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

from pydantic import ValidationError

from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.common import DataTypeKind, DataTypeSource
from score.ecu_model.data_types.identifier import Identifier
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType


class TestArrayDataType(unittest.TestCase):
    def test_creates_named_non_inline_array(self) -> None:
        array_type = ArrayDataType(
            name="IntArray",
            source_kind=DataTypeSource.FRANCA,
            data_type=PrimitiveDataType.INT32,
            dimension_min=0,
            dimension_max=10,
        )

        self.assertEqual(array_type.kind, DataTypeKind.ARRAY)
        self.assertEqual(str(array_type.name), "IntArray")
        self.assertFalse(array_type.is_inline)
        self.assertEqual(array_type.data_type, PrimitiveDataType.INT32)
        self.assertEqual(array_type.dimension_min, 0)
        self.assertEqual(array_type.dimension_max, 10)

    def test_creates_inline_array_without_identifier(self) -> None:
        array_type = ArrayDataType(
            source_kind=DataTypeSource.FRANCA,
            data_type=PrimitiveDataType.UINT8,
            is_inline=True,
            dimension_max=256,
        )

        self.assertIsNone(array_type.name)
        self.assertTrue(array_type.is_inline)
        self.assertEqual(array_type.data_type, PrimitiveDataType.UINT8)
        self.assertEqual(array_type.dimension_max, 256)
        with self.assertRaisesRegex(ValueError, "Data types without an identifier do not have a fully qualified name"):
            _ = array_type.fully_qualified_name

    def test_rejects_inline_array_with_identifier(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            ArrayDataType(
                name="BadInline",
                source_kind=DataTypeSource.FRANCA,
                data_type=PrimitiveDataType.UINT8,
                is_inline=True,
            )
        self.assertIn("inline arrays must not have an identifier", str(ctx.exception))

    def test_rejects_inline_array_with_namespace(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            ArrayDataType(
                name="InlineArray",
                namespace=("com", "example"),
                source_kind=DataTypeSource.FRANCA,
                data_type=PrimitiveDataType.UINT8,
                is_inline=True,
            )
        self.assertIn("inline arrays must not have an identifier", str(ctx.exception))

    def test_rejects_non_inline_array_without_identifier(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            ArrayDataType(
                source_kind=DataTypeSource.FRANCA,
                data_type=PrimitiveDataType.UINT8,
                is_inline=False,
            )
        self.assertIn("non-inline arrays require an identifier", str(ctx.exception))

    def test_rejects_negative_dimension_bounds(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            ArrayDataType(
                name="NegativeBounds",
                source_kind=DataTypeSource.FRANCA,
                data_type=PrimitiveDataType.UINT8,
                dimension_min=-1,
            )
        self.assertIn("array dimension bounds must be non-negative", str(ctx.exception))

    def test_rejects_invalid_dimension_range(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            ArrayDataType(
                name="BadRange",
                source_kind=DataTypeSource.FRANCA,
                data_type=PrimitiveDataType.UINT8,
                dimension_min=10,
                dimension_max=5,
            )
        self.assertIn("dimension_min must not be greater than dimension_max", str(ctx.exception))

    def test_supports_declared_type_ref_as_element_data_type(self) -> None:
        element_struct = StructDataType(name="Point", source_kind=DataTypeSource.FRANCA)
        array_type = ArrayDataType(
            name="PointArray",
            source_kind=DataTypeSource.FRANCA,
            data_type=element_struct,
        )

        self.assertIs(array_type.data_type, element_struct)

    def test_finalize_checks_element_data_type(self) -> None:
        array_type = ArrayDataType(
            name="PointArray",
            source_kind=DataTypeSource.FRANCA,
            data_type=Identifier("Point"),
        )

        with self.assertRaises(TypeError):
            array_type.finalize()

    def test_finalize_accepts_resolved_element_data_type(self) -> None:
        element_struct = StructDataType(name="Point", source_kind=DataTypeSource.FRANCA)
        array_type = ArrayDataType(
            name="PointArray",
            source_kind=DataTypeSource.FRANCA,
            data_type=element_struct,
        )

        array_type.finalize()


if __name__ == "__main__":
    unittest.main()
