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
from typing import Literal

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from score.ecu_model.data_types.common import (
    CustomDataType,
    DataType,
    DataTypeBase,
    DataTypeKind,
    DataTypeSource,
)
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.model import ModelRegistry


class StructMember(BaseModel):
    """Minimal struct member used to exercise type references in the tests."""

    identifier: str
    type: DataType


class StructDataType(DataTypeBase):
    """Minimal struct definition used to exercise type references in the tests."""

    kind: Literal[DataTypeKind.STRUCT] = Field(default=DataTypeKind.STRUCT, frozen=True)
    members: list[StructMember] = Field(default_factory=list)


class TestDataTypeBaseCommon(unittest.TestCase):
    def test_primitive_is_not_a_declarable_kind(self) -> None:
        self.assertNotIn("primitive", {kind.value for kind in DataTypeKind})

    def test_kind_and_source_str_representation(self) -> None:
        self.assertEqual(str(DataTypeKind.STRUCT), "struct")
        self.assertEqual(str(DataTypeSource.FRANCA), "franca")
        self.assertEqual(str(DataTypeSource.CPP_HEADER_FILE), "cpp_header_file")

    def test_optional_fields_defaults_and_values(self) -> None:
        data_type = StructDataType(
            kind=DataTypeKind.STRUCT,
            name="MyStruct",
            source_kind=DataTypeSource.FRANCA,
            source_uri="some/relative/path.fidl",
            deployment_properties={"key": "value"},
        )
        self.assertEqual(data_type.source_uri, "some/relative/path.fidl")
        self.assertEqual(data_type.deployment_properties, {"key": "value"})

    def test_rejects_empty_or_null_byte_source_uri(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            StructDataType(
                kind=DataTypeKind.STRUCT,
                name="MyStruct",
                source_kind=DataTypeSource.FRANCA,
                source_uri="   ",
            )
        self.assertIn("source_uri must not be empty", str(ctx.exception))

        with self.assertRaises(ValidationError) as ctx:
            StructDataType(
                kind=DataTypeKind.STRUCT,
                name="MyStruct",
                source_kind=DataTypeSource.FRANCA,
                source_uri="invalid\x00path",
            )
        self.assertIn("source_uri must not contain null bytes", str(ctx.exception))

    def test_rejects_direct_instantiation(self) -> None:
        with self.assertRaisesRegex(TypeError, "DataTypeBase is abstract"):
            DataTypeBase(
                kind=DataTypeKind.STRUCT,
                name="MyStruct",
                source_kind=DataTypeSource.FRANCA,
            )

    def test_rejects_none_identifier_for_non_array_types(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            StructDataType(
                kind=DataTypeKind.STRUCT,
                name=None,  # type: ignore[arg-type]
                source_kind=DataTypeSource.FRANCA,
            )
        self.assertIn("Input should be a valid string", str(ctx.exception))

    def test_custom_data_type_rejects_direct_instantiation(self) -> None:
        with self.assertRaisesRegex(TypeError, "CustomDataType is abstract"):
            CustomDataType()


class SampleCustomType(CustomDataType):
    """Custom pluggable data type used to test injection as DataType."""

    name: str
    payload_type: DataType


class TestTypeRef(unittest.TestCase):
    adapter = TypeAdapter(DataType)

    def test_primitive_is_referenced_by_canonical_name(self) -> None:
        self.assertIs(self.adapter.validate_python("uint32"), PrimitiveDataType.UINT32)

    def test_declared_type_is_referenced_by_direct_instance(self) -> None:
        definition = StructDataType(name="Position", source_kind=DataTypeSource.FRANCA)

        ref = self.adapter.validate_python(definition)

        self.assertIs(ref, definition)

    def test_custom_data_type_is_referenced_by_direct_instance(self) -> None:
        custom_type = SampleCustomType(name="VehicleSpeedType", payload_type=PrimitiveDataType.FLOAT)

        ref = self.adapter.validate_python(custom_type)

        self.assertIs(ref, custom_type)

    def test_unknown_primitive_name_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.adapter.validate_python("uint24")


class TestDirectDataTypeReferences(unittest.TestCase):
    def test_reference_is_the_same_object_as_the_target(self) -> None:
        definition = StructDataType(name="Position", source_kind=DataTypeSource.FRANCA)

        member = StructMember(identifier="position", type=definition)

        self.assertIs(member.type, definition)

    def test_custom_data_type_can_be_used_as_struct_member_type(self) -> None:
        custom_type = SampleCustomType(name="VehicleSpeedType", payload_type=PrimitiveDataType.FLOAT)

        member = StructMember(identifier="speed_type", type=custom_type)

        self.assertIs(member.type, custom_type)


class TestPickleRoundTrip(unittest.TestCase):
    """Example: persist the whole type graph and make it resolvable again."""

    def setUp(self) -> None:
        self._saved_registry = dict(ModelRegistry.elements)
        ModelRegistry.elements.clear()

    def tearDown(self) -> None:
        ModelRegistry.elements.clear()
        ModelRegistry.elements.update(self._saved_registry)

    @staticmethod
    def _build_type_graph() -> tuple[DataTypeBase, DataTypeBase]:
        position = StructDataType(
            name="Position",
            namespace=("app", "geometry"),
            source_kind=DataTypeSource.FRANCA,
            members=[
                StructMember(identifier="x", type=PrimitiveDataType.FLOAT),
                StructMember(identifier="y", type=PrimitiveDataType.FLOAT),
            ],
        )
        waypoint = StructDataType(
            name="Waypoint",
            namespace=("app", "routing"),
            source_kind=DataTypeSource.FRANCA,
            members=[
                StructMember(identifier="position", type=position),
                StructMember(identifier="index", type=PrimitiveDataType.UINT32),
            ],
        )
        return position, waypoint

    def test_references_resolve_again_after_round_trip(self) -> None:
        position, waypoint = self._build_type_graph()
        blob = ModelRegistry.serialize()
        ModelRegistry.elements.clear()  # simulate loading into a fresh process

        # 2 structs
        self.assertEqual(ModelRegistry.deserialize(blob), 2)

        restored_waypoint = ModelRegistry.elements[waypoint.id]
        assert isinstance(restored_waypoint, StructDataType)
        restored_position = ModelRegistry.elements[position.id]

        self.assertIs(restored_waypoint.members[0].type, restored_position)
        self.assertIsNot(restored_position, position)

    def test_round_trip_preserves_identifiers_and_primitive_members(self) -> None:
        position, _ = self._build_type_graph()
        blob = ModelRegistry.serialize()
        ModelRegistry.elements.clear()

        ModelRegistry.deserialize(blob)

        restored = ModelRegistry.elements[position.id]
        assert isinstance(restored, StructDataType)
        self.assertEqual(str(restored.name), "Position")
        self.assertEqual(restored.members[0].type, PrimitiveDataType.FLOAT)


if __name__ == "__main__":
    unittest.main()
