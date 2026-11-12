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

from score.ecu_model.data_types.common import DataTypeKind, DataTypeSource
from score.ecu_model.data_types.composite import CompositeDataType, DataTypeField
from score.ecu_model.data_types.enum import EnumDataType
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.model import ModelRegistry


class TestCompositeDataType(unittest.TestCase):
    def setUp(self) -> None:
        ModelRegistry.elements.clear()
        self.addCleanup(ModelRegistry.elements.clear)

    def test_fields_keep_identity_without_independent_registration(self) -> None:
        """Registry serialization retains owned fields and their shared type references."""
        child = StructDataType(name="Child", source_kind=DataTypeSource.FRANCA)
        field = DataTypeField(name="child", data_type=child, description="Child member")
        parent = StructDataType(name="Parent", source_kind=DataTypeSource.FRANCA, fields=[field])

        self.assertEqual(ModelRegistry.elements, {child.id: child, parent.id: parent})
        self.assertNotIn(field.id, ModelRegistry.elements)

        restored_count = ModelRegistry.deserialize(ModelRegistry.serialize())
        restored_parent = ModelRegistry.elements[parent.id]
        restored_field = restored_parent.fields[0]

        self.assertEqual(restored_count, 2)
        self.assertEqual(restored_field.id, field.id)
        self.assertEqual(restored_field.description, "Child member")
        self.assertIs(restored_field.data_type, ModelRegistry.elements[child.id])
        self.assertNotIn(field.id, ModelRegistry.elements)

    @staticmethod
    def _field(identifier: str, field_number: int | None = None) -> DataTypeField:
        return DataTypeField(
            name=identifier,
            data_type=PrimitiveDataType.UINT32,
            field_number=field_number,
        )

    def test_rejects_direct_instantiation_of_the_abstract_base(self) -> None:
        with self.assertRaisesRegex(TypeError, "CompositeDataType is abstract"):
            CompositeDataType(
                name="Position",
                kind=DataTypeKind.STRUCT,
                source_kind=DataTypeSource.FRANCA,
            )

    def test_does_not_register_the_rejected_instance(self) -> None:
        registered_elements = len(ModelRegistry.elements)

        with self.assertRaises(TypeError):
            CompositeDataType(
                name="Position",
                kind=DataTypeKind.STRUCT,
                source_kind=DataTypeSource.FRANCA,
            )

        self.assertEqual(len(ModelRegistry.elements), registered_elements)

    def test_rejects_invalid_or_duplicate_field_identifiers(self) -> None:
        with self.assertRaisesRegex(ValidationError, "Invalid identifier '1field'"):
            StructDataType(
                name="Position",
                source_kind=DataTypeSource.FRANCA,
                fields=[self._field("1field")],
            )

        with self.assertRaisesRegex(ValidationError, "field identifiers must be unique"):
            StructDataType(
                name="Position",
                source_kind=DataTypeSource.FRANCA,
                fields=[self._field("field"), self._field("field")],
            )

    def test_allows_mixed_field_numbers(self) -> None:
        data_type = StructDataType(
            name="Position",
            source_kind=DataTypeSource.PROTOBUF,
            fields=[self._field("x", 1), self._field("y")],
        )

        self.assertEqual([field.field_number for field in data_type.fields], [1, None])

    def test_rejects_duplicate_field_numbers(self) -> None:
        with self.assertRaisesRegex(ValidationError, "explicit field numbers must be unique"):
            StructDataType(
                name="Position",
                source_kind=DataTypeSource.PROTOBUF,
                fields=[self._field("x", 1), self._field("y", 1)],
            )

    def test_rejects_invalid_field_numbers(self) -> None:
        with self.assertRaisesRegex(ValidationError, "field number must be positive"):
            DataTypeField(name="field", data_type=PrimitiveDataType.UINT32, field_number=0)

        with self.assertRaisesRegex(ValidationError, "field number must be an integer, not boolean"):
            DataTypeField(name="field", data_type=PrimitiveDataType.UINT32, field_number=True)

    def test_revalidates_fields_on_assignment(self) -> None:
        data_type = StructDataType(
            name="Position",
            source_kind=DataTypeSource.FRANCA,
            fields=[self._field("field")],
        )

        with self.assertRaisesRegex(ValidationError, "field identifiers must be unique"):
            data_type.fields = (self._field("field"), self._field("field"))

    def test_allows_franca_inheritance_only(self) -> None:
        parent = StructDataType(name="BasePosition", source_kind=DataTypeSource.FRANCA)
        child = StructDataType(
            name="Position",
            source_kind=DataTypeSource.FRANCA,
            extends=parent,
        )
        self.assertIs(child.extends, parent)

        with self.assertRaisesRegex(
            ValidationError, "StructDataType inheritance is only allowed for FRANCA source kind"
        ):
            StructDataType(
                name="Position",
                source_kind=DataTypeSource.PROTOBUF,
                extends=parent,
            )

    def test_rejects_extending_base_type_of_different_kind(self) -> None:
        parent_enum = EnumDataType(name="BaseEnum", source_kind=DataTypeSource.FRANCA)

        with self.assertRaisesRegex(ValidationError, "can only extend another data type of kind 'struct'"):
            StructDataType(
                name="ChildStruct",
                source_kind=DataTypeSource.FRANCA,
                extends=parent_enum,
            )

    def test_accepts_elements_in_place_of_references(self) -> None:
        parent = StructDataType(name="BasePosition", source_kind=DataTypeSource.FRANCA)
        field = DataTypeField(name="x", data_type=PrimitiveDataType.UINT32)

        data_type = StructDataType(
            name="Position",
            source_kind=DataTypeSource.FRANCA,
            extends=parent,
            fields=[field],
        )

        self.assertIs(data_type.extends, parent)
        self.assertIs(data_type.fields[0], field)


if __name__ == "__main__":
    unittest.main()
