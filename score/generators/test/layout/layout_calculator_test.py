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

"""Verify the documented member layout selection using resolved ECU models."""

import unittest

from score.ecu_model.common.version import Version
from score.ecu_model.communication.service_interface import (
    Attribute,
    Broadcast,
    InterfaceDefinition,
    Method,
    ServiceInterface,
)
from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.common import DataTypeOrReference, DataTypeSource
from score.ecu_model.data_types.composite import DataTypeField
from score.ecu_model.data_types.identifier import Identifier, QualifiedName, SelectableIdentifier
from score.ecu_model.data_types.map import MapDataType
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.data_types.union import UnionDataType
from score.ecu_model.model import ModelRegistry
from score.generators.src.layout.element_layout import ByteOrder, ElementLayout, StringEncoding
from score.generators.src.layout.layout_calculator import calculate_interface_layouts

type _Member = Attribute | Method | Broadcast
type _Properties = dict[str, object]

_LOGGER = "score.generators.src.layout.layout_calculator"


class LayoutCalculatorTest(unittest.TestCase):
    """Check precedence, traversal, validation, and reuse through the public API."""

    def setUp(self) -> None:
        """Isolate both registries and restore their original dictionary objects."""
        original_models = ModelRegistry.elements
        original_layouts = ElementLayout._instances
        ModelRegistry.elements = {}
        ElementLayout._instances = {}
        self.addCleanup(setattr, ModelRegistry, "elements", original_models)
        self.addCleanup(setattr, ElementLayout, "_instances", original_layouts)

    @staticmethod
    def _service(*members: _Member, properties: dict[str, _Properties] | None = None) -> ServiceInterface:
        """Wrap every declaration with a matching, fully covered deployment map."""
        properties = {} if properties is None else properties
        attributes = {member.name: member for member in members if isinstance(member, Attribute)}
        methods = {member.name: member for member in members if isinstance(member, Method)}
        broadcasts = {member.name: member for member in members if isinstance(member, Broadcast)}
        design = InterfaceDefinition(
            name=Identifier("Demo"),
            version=Version(),
            attributes=attributes,
            methods=methods,
            broadcasts=broadcasts,
        )
        return ServiceInterface(
            name=Identifier("DemoDeployment"),
            design_element=design,
            attribute_deployment_properties={name: properties.get(str(name), {}) for name in attributes},
            method_deployment_properties={name: properties.get(str(name), {}) for name in methods},
            broadcast_deployment_properties={name: properties.get(str(name), {}) for name in broadcasts},
        )

    def _calculate(self, member: _Member, properties: _Properties | None = None) -> ElementLayout:
        """Calculate through a valid concrete service rather than a model mock."""
        service = self._service(member, properties={str(member.name): {} if properties is None else properties})
        return calculate_interface_layouts(service)[member.id]

    @staticmethod
    def _field(name: str, data_type: DataTypeOrReference, properties: _Properties | None = None) -> DataTypeField:
        return DataTypeField(
            name=Identifier(name),
            data_type=data_type,
            deployment_properties={} if properties is None else properties,
        )

    @staticmethod
    def _array(
        data_type: DataTypeOrReference = PrimitiveDataType.UINT16,
        *,
        name: str | None = None,
        width: int | None = None,
        bounds: tuple[int, int] = (0, 8),
        properties: _Properties | None = None,
    ) -> ArrayDataType:
        """Give named arrays explicit bounds so width tests do not fail on bounds."""
        deployment = {} if properties is None else dict(properties)
        if width is not None:
            deployment["SomeIpArrayLengthWidth"] = width
        return ArrayDataType(
            source_kind=DataTypeSource.FRANCA,
            name=None if name is None else Identifier(name),
            is_inline=name is None,
            data_type=data_type,
            dimension_min=bounds[0],
            dimension_max=bounds[1],
            deployment_properties=deployment,
        )

    @staticmethod
    def _string_properties(encoding: str = "utf8", width: int = 4) -> _Properties:
        return {"SomeIpStringEncoding": encoding, "SomeIpStringLengthWidth": width}

    @classmethod
    def _string_type(cls, name: str, encoding: str = "utf8", width: int = 4) -> TypedefDataType:
        return TypedefDataType(
            name=Identifier(name),
            source_kind=DataTypeSource.FRANCA,
            data_type=PrimitiveDataType.STRING,
            deployment_properties=cls._string_properties(encoding, width),
        )

    def _assert_layout(
        self,
        layout: ElementLayout,
        *,
        byte_order: ByteOrder = ByteOrder.BIG_ENDIAN,
        vector: int = 4,
        string: int = 4,
        struct: int = 0,
        encoding: StringEncoding = StringEncoding.UTF8,
    ) -> None:
        """Assert all six fields and their public identifier, not only one width."""
        self.assertEqual(
            (
                layout.byte_order,
                layout.alignment_bits,
                layout.vector_length_field_bytes,
                layout.string_length_field_bytes,
                layout.struct_length_field_bytes,
                layout.string_encoding,
            ),
            (byte_order, 8, vector, string, struct, encoding),
        )
        self.assertEqual(layout.layout_id, f"{byte_order.value}_8_{vector}_{string}_{struct}_{encoding.value}")
        self.assertIs(ElementLayout.find(layout.layout_id), layout)

    def test_defaults_and_sharing_across_all_member_kinds(self) -> None:
        attribute = Attribute(name=Identifier("number"), data_type=PrimitiveDataType.UINT32)
        method = Method(name=SelectableIdentifier("call"))
        broadcast = Broadcast(name=SelectableIdentifier("event"))
        service = self._service(attribute, method, broadcast)
        with self.assertNoLogs(_LOGGER, level="WARNING"):
            member_layouts = calculate_interface_layouts(service)
        self.assertEqual(list(member_layouts), [attribute.id, method.id, broadcast.id])
        layouts = list(member_layouts.values())
        for layout in layouts:
            self._assert_layout(layout)
            self.assertIs(layout, layouts[0])
        self.assertEqual(len(ElementLayout._instances), 1)

    def test_interface_without_members_has_no_layouts(self) -> None:
        self.assertEqual(calculate_interface_layouts(self._service()), {})
        self.assertEqual(ElementLayout._instances, {})

    def test_same_named_member_kinds_keep_distinct_ids_and_deployments(self) -> None:
        attribute = Attribute(name=Identifier("shared"), data_type=PrimitiveDataType.STRING)
        method = Method(name=SelectableIdentifier("shared"))
        broadcast = Broadcast(name=SelectableIdentifier("shared"))
        service = self._service(attribute, method, broadcast)
        service.attribute_deployment_properties[attribute.name].update(self._string_properties("utf16be", 2))
        service.method_deployment_properties[method.name]["SomeIpMethodEndianess"] = "le"

        layouts = calculate_interface_layouts(service)

        self.assertEqual(list(layouts), [attribute.id, method.id, broadcast.id])
        self._assert_layout(layouts[attribute.id], string=2, encoding=StringEncoding.UTF16)
        self._assert_layout(layouts[method.id], byte_order=ByteOrder.LITTLE_ENDIAN)
        self._assert_layout(layouts[broadcast.id])

    def test_interface_follows_member_declaration_order_not_deployment_order(self) -> None:
        first = Attribute(name=Identifier("first"), data_type=PrimitiveDataType.UINT32)
        second = Attribute(name=Identifier("second"), data_type=PrimitiveDataType.UINT32)
        service = self._service(first, second, properties={"second": {"SomeIpAttributeEndianess": "le"}})
        service.attribute_deployment_properties = dict(reversed(tuple(service.attribute_deployment_properties.items())))

        layouts = calculate_interface_layouts(service)

        self.assertEqual(list(layouts), [first.id, second.id])
        self._assert_layout(layouts[first.id])
        self._assert_layout(layouts[second.id], byte_order=ByteOrder.LITTLE_ENDIAN)

    def test_shared_design_uses_each_service_deployment_without_mutation(self) -> None:
        attribute = Attribute(name=Identifier("number"), data_type=PrimitiveDataType.UINT32)
        big = self._service(attribute)
        little = ServiceInterface(
            name=Identifier("LittleDeployment"),
            design_element=big.design_element,
            attribute_deployment_properties={attribute.name: {"SomeIpAttributeEndianess": "le"}},
        )
        before = ModelRegistry.serialize()

        big_layouts = calculate_interface_layouts(big)
        little_layouts = calculate_interface_layouts(little)

        self.assertEqual(list(big_layouts), [attribute.id])
        self.assertEqual(list(little_layouts), [attribute.id])
        self._assert_layout(big_layouts[attribute.id])
        self._assert_layout(little_layouts[attribute.id], byte_order=ByteOrder.LITTLE_ENDIAN)
        self.assertEqual(ModelRegistry.serialize(), before)

    def test_each_member_reads_its_corresponding_endian_property(self) -> None:
        members = (
            (Attribute(name=Identifier("number"), data_type=PrimitiveDataType.UINT32), "SomeIpAttributeEndianess"),
            (Method(name=SelectableIdentifier("call")), "SomeIpMethodEndianess"),
            (Broadcast(name=SelectableIdentifier("event")), "SomeIpBroadcastEndianess"),
        )
        for member, property_name in members:
            with self.subTest(member=type(member).__name__):
                self._assert_layout(self._calculate(member, {property_name: "le"}), byte_order=ByteOrder.LITTLE_ENDIAN)

    def test_documented_status_uses_samples_two_not_member_four(self) -> None:
        status_type = StructDataType(
            name=Identifier("Status"),
            source_kind=DataTypeSource.FRANCA,
            deployment_properties={"SomeIpStructLengthWidth": 0},
            fields=(
                self._field("counter", PrimitiveDataType.UINT32),
                self._field("samples", self._array(), {"SomeIpArrayLengthWidth": 2}),
            ),
        )
        status = Attribute(name=Identifier("status"), data_type=status_type)
        with self.assertNoLogs(_LOGGER, level="WARNING"):
            layout = self._calculate(
                status,
                {"SomeIpAttributeEndianess": "le", "SomeIpStructLengthWidth": 0, "SomeIpArrayLengthWidth": 4},
            )
        self._assert_layout(layout, byte_order=ByteOrder.LITTLE_ENDIAN, vector=2)
        self.assertEqual(layout.layout_id, "LittleEndian_8_2_4_0_Utf8")

    def test_array_width_first_valid_preserves_zero_without_conflict_warnings(self) -> None:
        for first_width in (0, 2):
            with self.subTest(first_width=first_width):
                data_type = StructDataType(
                    name=Identifier("Arrays"),
                    source_kind=DataTypeSource.FRANCA,
                    fields=(
                        self._field("primitive", PrimitiveDataType.UINT32, {"SomeIpArrayLengthWidth": 1}),
                        self._field("unconfigured", self._array()),
                        self._field("first", self._array(), {"SomeIpArrayLengthWidth": first_width}),
                        self._field("later", self._array(), {"SomeIpArrayLengthWidth": 4}),
                    ),
                )
                with self.assertNoLogs(_LOGGER, level="WARNING"):
                    layout = self._calculate(Attribute(name=Identifier("arrays"), data_type=data_type))
                self._assert_layout(layout, vector=first_width)

    def test_method_inputs_precede_outputs_for_arrays_and_strings(self) -> None:
        method = Method(
            name=SelectableIdentifier("call"),
            inputs=[
                self._field("number", PrimitiveDataType.UINT32),
                self._field("request", self._array(), {"SomeIpArrayLengthWidth": 2}),
                self._field("requestText", PrimitiveDataType.STRING, self._string_properties("utf16le", 0)),
            ],
            outputs=[
                self._field("response", self._array(), {"SomeIpArrayLengthWidth": 4}),
                self._field("responseText", PrimitiveDataType.STRING, self._string_properties("utf8", 4)),
            ],
        )
        with self.assertLogs(_LOGGER, level="WARNING") as logs:
            layout = self._calculate(
                method,
                {"SomeIpMethodEndianess": "le", "SomeIpArrayLengthWidth": 1, **self._string_properties("utf16be", 2)},
            )
        self._assert_layout(
            layout, byte_order=ByteOrder.LITTLE_ENDIAN, vector=2, string=0, encoding=StringEncoding.UTF16
        )
        self.assertTrue(any("conflicting string encodings" in message for message in logs.output))

    def test_method_falls_through_unconfigured_inputs_to_outputs(self) -> None:
        method = Method(
            name=SelectableIdentifier("call"),
            inputs=[self._field("input", self._array())],
            outputs=[
                self._field("output", self._array(), {"SomeIpArrayLengthWidth": 0}),
                self._field("text", PrimitiveDataType.STRING, self._string_properties("utf16be", 2)),
            ],
        )
        self._assert_layout(self._calculate(method), vector=0, string=2, encoding=StringEncoding.UTF16)

    def test_broadcast_outputs_follow_declaration_order(self) -> None:
        broadcast = Broadcast(
            name=SelectableIdentifier("event"),
            outputs=[
                self._field("number", PrimitiveDataType.UINT32),
                self._field("firstArray", self._array(), {"SomeIpArrayLengthWidth": 0}),
                self._field("laterArray", self._array(), {"SomeIpArrayLengthWidth": 2}),
                self._field("firstText", PrimitiveDataType.STRING, self._string_properties("utf8", 2)),
                self._field("laterText", PrimitiveDataType.STRING, self._string_properties("utf16be", 4)),
            ],
        )
        with self.assertLogs(_LOGGER, level="WARNING") as logs:
            layout = self._calculate(broadcast, {"SomeIpArrayLengthWidth": 4, **self._string_properties("utf16le", 0)})
        self._assert_layout(layout, vector=0, string=2)
        self.assertTrue(any("conflicting string encodings" in message for message in logs.output))

    def test_method_and_broadcast_ignore_member_array_and_string_configuration(self) -> None:
        for member in (Method(name=SelectableIdentifier("call")), Broadcast(name=SelectableIdentifier("event"))):
            with self.subTest(member=type(member).__name__):
                with self.assertNoLogs(_LOGGER, level="WARNING"):
                    layout = self._calculate(
                        member, {"SomeIpArrayLengthWidth": 0, **self._string_properties("utf16le", 0)}
                    )
                self._assert_layout(layout)

    def test_method_and_broadcast_struct_width_is_zero_at_every_source(self) -> None:
        nested = StructDataType(
            name=Identifier("Nested"),
            source_kind=DataTypeSource.FRANCA,
            deployment_properties={"SomeIpStructLengthWidth": 4},
        )
        data_type = StructDataType(
            name=Identifier("Payload"),
            source_kind=DataTypeSource.FRANCA,
            deployment_properties={"SomeIpStructLengthWidth": 2},
            fields=(self._field("nested", nested, {"SomeIpStructLengthWidth": 3}),),
        )
        parameter = self._field("payload", data_type, {"SomeIpStructLengthWidth": 1})
        members = (
            Method(name=SelectableIdentifier("call"), inputs=[parameter], outputs=[parameter]),
            Broadcast(name=SelectableIdentifier("event"), outputs=[parameter]),
        )
        for member in members:
            with self.subTest(member=type(member).__name__):
                self._assert_layout(self._calculate(member, {"SomeIpStructLengthWidth": 4}))

    def test_string_local_candidates_precede_type_and_warn(self) -> None:
        attribute = Attribute(name=Identifier("text"), data_type=self._string_type("Text", "utf16le", 4))
        data_type = StructDataType(
            name=Identifier("Payload"),
            source_kind=DataTypeSource.FRANCA,
            fields=(self._field("text", self._string_type("Text", "utf16le", 4), self._string_properties("utf8", 2)),),
        )
        scenarios = (
            ("attribute", attribute, self._string_properties("utf8", 0), 0),
            ("field", Attribute(name=Identifier("payload"), data_type=data_type), None, 2),
        )
        for source, member, properties, expected_width in scenarios:
            with self.subTest(source=source):
                with self.assertLogs(_LOGGER, level="WARNING") as logs:
                    layout = self._calculate(member, properties)
                self._assert_layout(layout, string=expected_width)
                self.assertTrue(any("conflicting string encodings" in message for message in logs.output))

    def test_type_string_candidate_is_used_without_local_encoding(self) -> None:
        attribute = Attribute(name=Identifier("text"), data_type=self._string_type("Text", "utf16be", 2))
        with self.assertNoLogs(_LOGGER, level="WARNING"):
            layout = self._calculate(attribute, {"SomeIpStringLengthWidth": 0})
        self._assert_layout(layout, string=2, encoding=StringEncoding.UTF16)

    def test_string_candidates_compare_the_whole_tuple(self) -> None:
        scenarios = (
            ("width", "utf8", 0, "utf8", 4, StringEncoding.UTF8, True),
            ("encoding", "utf8", 2, "utf16be", 2, StringEncoding.UTF8, True),
            ("endian", "utf16be", 2, "utf16le", 2, StringEncoding.UTF16, True),
            ("identical", "utf16be", 0, "utf16be", 0, StringEncoding.UTF16, False),
        )
        for label, first_encoding, first_width, later_encoding, later_width, expected_encoding, warns in scenarios:
            with self.subTest(difference=label):
                method = Method(
                    name=SelectableIdentifier("call"),
                    inputs=[
                        self._field(
                            "first", PrimitiveDataType.STRING, self._string_properties(first_encoding, first_width)
                        )
                    ],
                    outputs=[
                        self._field(
                            "later", PrimitiveDataType.STRING, self._string_properties(later_encoding, later_width)
                        )
                    ],
                )
                if warns:
                    with self.assertLogs(_LOGGER, level="WARNING") as logs:
                        layout = self._calculate(method)
                    self.assertTrue(any("conflicting string encodings" in message for message in logs.output))
                else:
                    with self.assertNoLogs(_LOGGER, level="WARNING"):
                        layout = self._calculate(method)
                self._assert_layout(layout, string=first_width, encoding=expected_encoding)

    def test_selected_string_with_wrong_endian_raises_without_interning(self) -> None:
        for encoding, endian in (("utf16le", "be"), ("utf16be", "le")):
            parameter = self._field("text", PrimitiveDataType.STRING, self._string_properties(encoding, 2))
            scenarios = (
                (Attribute(name=Identifier("text"), data_type=PrimitiveDataType.STRING), "SomeIpAttributeEndianess"),
                (Method(name=SelectableIdentifier("call"), inputs=[parameter]), "SomeIpMethodEndianess"),
                (Broadcast(name=SelectableIdentifier("event"), outputs=[parameter]), "SomeIpBroadcastEndianess"),
            )
            for member, endian_property in scenarios:
                with self.subTest(member=type(member).__name__, encoding=encoding, endian=endian):
                    properties = {endian_property: endian}
                    if isinstance(member, Attribute):
                        properties.update(self._string_properties(encoding, 2))
                    with self.assertRaisesRegex(RuntimeError, "conflicting endianess"):
                        self._calculate(member, properties)
                    self.assertEqual(ElementLayout._instances, {})

    def test_shared_types_reuse_equal_layouts_and_separate_struct_width_without_mutation(self) -> None:
        nested = StructDataType(
            name=Identifier("Nested"),
            source_kind=DataTypeSource.FRANCA,
            deployment_properties={"SomeIpStructLengthWidth": 2},
            fields=(self._field("values", self._array(width=4), {"SomeIpArrayLengthWidth": 2}),),
        )
        data_type = StructDataType(
            name=Identifier("Shared"),
            source_kind=DataTypeSource.FRANCA,
            deployment_properties={"SomeIpStructLengthWidth": 3},
            fields=(self._field("nested", nested, {"SomeIpStructLengthWidth": 1}),),
        )
        first, second, third = (
            Attribute(name=Identifier(name), data_type=data_type) for name in ("first", "second", "third")
        )
        service = self._service(
            first,
            second,
            third,
            properties={
                "first": {"SomeIpStructLengthWidth": 0},
                "second": {"SomeIpStructLengthWidth": 0},
                "third": {"SomeIpStructLengthWidth": 4},
            },
        )
        before = ModelRegistry.serialize()
        original_objects = dict(ModelRegistry.elements)
        layouts = calculate_interface_layouts(service)
        first_layout = layouts[first.id]
        second_layout = layouts[second.id]
        third_layout = layouts[third.id]
        self._assert_layout(first_layout, vector=2)
        self._assert_layout(second_layout, vector=2)
        self._assert_layout(third_layout, vector=2, struct=4)
        self.assertIs(first_layout, second_layout)
        self.assertIsNot(first_layout, third_layout)
        self.assertIs(calculate_interface_layouts(service)[first.id], first_layout)
        self.assertEqual(len(ElementLayout._instances), 2)
        self.assertEqual(ModelRegistry.serialize(), before)
        self.assertEqual(ModelRegistry.elements.keys(), original_objects.keys())
        for model_id, original in original_objects.items():
            self.assertIs(ModelRegistry.elements[model_id], original)
        for member in (first, second, third):
            self.assertIs(member.data_type, data_type)

    def test_inline_primitive_array_attribute_uses_member_width(self) -> None:
        attribute = Attribute(name=Identifier("values"), data_type=self._array(width=4))
        self._assert_layout(self._calculate(attribute, {"SomeIpArrayLengthWidth": 2}), vector=2)

    def test_inline_primitive_array_field_uses_field_width(self) -> None:
        method = Method(
            name=SelectableIdentifier("call"),
            inputs=[self._field("values", self._array(width=4), {"SomeIpArrayLengthWidth": 0})],
        )
        self._assert_layout(self._calculate(method, {"SomeIpArrayLengthWidth": 2}), vector=0)

    def test_inline_composite_array_recurses_to_element_configuration(self) -> None:
        element = StructDataType(
            name=Identifier("Element"),
            source_kind=DataTypeSource.FRANCA,
            fields=(self._field("values", self._array(), {"SomeIpArrayLengthWidth": 2}),),
        )
        attribute = Attribute(name=Identifier("elements"), data_type=self._array(element, width=1))
        self._assert_layout(
            self._calculate(attribute, {"SomeIpArrayLengthWidth": 4, "SomeIpStructLengthWidth": 3}), vector=2, struct=3
        )

    def test_named_array_uses_type_width_not_attribute_or_field_width(self) -> None:
        named = self._array(name="Values", width=2)
        attribute = Attribute(name=Identifier("values"), data_type=named)
        method = Method(
            name=SelectableIdentifier("call"), inputs=[self._field("values", named, {"SomeIpArrayLengthWidth": 0})]
        )
        for member in (attribute, method):
            with self.subTest(member=type(member).__name__):
                self._assert_layout(self._calculate(member, {"SomeIpArrayLengthWidth": 4}), vector=2)

    def test_named_array_bounds_control_fallback_and_preserve_explicit_zero(self) -> None:
        nested = self._array(name="Nested", width=2)
        scenarios = (
            ("Fixed", (3, 3), None, 2),
            ("Variable", (0, 8), None, 4),
            ("FixedZeroWidth", (3, 3), 0, 0),
            ("VariableZeroWidth", (0, 8), 0, 0),
            ("ZeroBound", (0, 0), None, 4),
        )
        for name, bounds, width, expected in scenarios:
            with self.subTest(name=name):
                attribute = Attribute(
                    name=Identifier("values"), data_type=self._array(nested, name=name, width=width, bounds=bounds)
                )
                self._assert_layout(self._calculate(attribute), vector=expected)

    def test_typedef_preserves_named_nested_array_reference_semantics(self) -> None:
        nested = self._array(name="Nested", width=2)
        outer = self._array(nested, name="Outer", width=4)
        alias = TypedefDataType(name=Identifier("Alias"), source_kind=DataTypeSource.FRANCA, data_type=outer)
        direct_attribute = Attribute(name=Identifier("direct"), data_type=outer)
        alias_attribute = Attribute(name=Identifier("alias"), data_type=alias)
        service = self._service(direct_attribute, alias_attribute)
        layouts = calculate_interface_layouts(service)
        self._assert_layout(layouts[direct_attribute.id], vector=4)
        self._assert_layout(layouts[alias_attribute.id], vector=4)

    def test_named_array_uses_deployed_bounds_and_rejects_disagreement(self) -> None:
        for prefix in ("SomeIp", "Ipc", "Persistency", "Diagnostic"):
            with self.subTest(prefix=prefix):
                array = ArrayDataType(
                    name="Values",
                    source_kind=DataTypeSource.FRANCA,
                    data_type=PrimitiveDataType.UINT16,
                    deployment_properties={
                        f"{prefix}ArrayMinLength": 0,
                        f"{prefix}ArrayMaxLength": 8,
                        "SomeIpArrayLengthWidth": 2,
                    },
                )
                self._assert_layout(self._calculate(Attribute(name=Identifier("values"), data_type=array)), vector=2)
        array = ArrayDataType(
            name="Conflict",
            source_kind=DataTypeSource.FRANCA,
            data_type=PrimitiveDataType.UINT16,
            deployment_properties={"SomeIpArrayMinLength": 0, "IpcArrayMinLength": 1, "SomeIpArrayMaxLength": 8},
        )
        with self.assertRaisesRegex(ValueError, "Conflicting array MinLength"):
            self._calculate(Attribute(name=Identifier("values"), data_type=array))

    def test_mixed_string_map_picks_map_and_nested_candidates(self) -> None:
        nested_type = self._string_type("Text", "utf16be", 4)
        scenarios = (
            ("map-first", self._string_properties("utf8", 2), 2, StringEncoding.UTF8, True),
            ("nested-fallback", {}, 4, StringEncoding.UTF16, False),
        )
        for name, properties, expected_width, expected_encoding, warns in scenarios:
            with self.subTest(scenario=name):
                mapping = MapDataType(
                    name="Lookup",
                    source_kind=DataTypeSource.FRANCA,
                    key_type=PrimitiveDataType.STRING,
                    value_type=nested_type,
                    deployment_properties=properties,
                )
                attribute = Attribute(name=Identifier("lookup"), data_type=mapping)
                if warns:
                    with self.assertLogs(_LOGGER, level="WARNING") as logs:
                        layout = self._calculate(attribute)
                    self.assertTrue(any("conflicting string encodings" in message for message in logs.output))
                else:
                    with self.assertNoLogs(_LOGGER, level="WARNING"):
                        layout = self._calculate(attribute)
                self._assert_layout(layout, string=expected_width, encoding=expected_encoding)

    def test_attribute_struct_predicate_does_not_expand_typedef_or_named_array(self) -> None:
        structure = StructDataType(
            name=Identifier("Payload"),
            source_kind=DataTypeSource.FRANCA,
            deployment_properties={"SomeIpStructLengthWidth": 4},
        )
        inline = self._array(structure)
        scenarios = (
            ("direct", structure, 2),
            ("inline", inline, 2),
            ("named", self._array(structure, name="Payloads", width=4), 0),
            (
                "alias",
                TypedefDataType(name=Identifier("Alias"), source_kind=DataTypeSource.FRANCA, data_type=structure),
                0,
            ),
            (
                "inlineAlias",
                TypedefDataType(name=Identifier("InlineAlias"), source_kind=DataTypeSource.FRANCA, data_type=inline),
                0,
            ),
        )
        for name, data_type, expected in scenarios:
            with self.subTest(name=name):
                self._assert_layout(
                    self._calculate(
                        Attribute(name=Identifier(name), data_type=data_type), {"SomeIpStructLengthWidth": 2}
                    ),
                    struct=expected,
                )
        self._assert_layout(self._calculate(Attribute(name=Identifier("missing"), data_type=structure)))

    def test_struct_base_first_and_union_local_first_for_arrays_and_strings(self) -> None:
        for composite_type, vector, string, encoding in (
            (StructDataType, 2, 2, StringEncoding.UTF8),
            (UnionDataType, 0, 4, StringEncoding.UTF16),
        ):
            with self.subTest(composite=composite_type.__name__):
                base = composite_type(
                    name=Identifier("Base"),
                    source_kind=DataTypeSource.FRANCA,
                    fields=(
                        self._field("baseArray", self._array(), {"SomeIpArrayLengthWidth": 2}),
                        self._field("baseText", PrimitiveDataType.STRING, self._string_properties("utf8", 2)),
                    ),
                )
                derived = composite_type(
                    name=Identifier("Derived"),
                    source_kind=DataTypeSource.FRANCA,
                    extends=base,
                    fields=(
                        self._field("localArray", self._array(), {"SomeIpArrayLengthWidth": 0}),
                        self._field("localText", PrimitiveDataType.STRING, self._string_properties("utf16be", 4)),
                    ),
                )
                with self.assertLogs(_LOGGER, level="WARNING") as logs:
                    layout = self._calculate(Attribute(name=Identifier("payload"), data_type=derived))
                self._assert_layout(layout, vector=vector, string=string, encoding=encoding)
                self.assertTrue(any("conflicting string encodings for Derived" in message for message in logs.output))

    def test_numeric_map_does_not_use_map_string_or_array_properties(self) -> None:
        data_type = MapDataType(
            name=Identifier("Numbers"),
            source_kind=DataTypeSource.FRANCA,
            key_type=PrimitiveDataType.UINT16,
            value_type=PrimitiveDataType.UINT32,
            deployment_properties={"SomeIpArrayLengthWidth": 0, **self._string_properties("utf16le", 0)},
        )
        with self.assertNoLogs(_LOGGER, level="WARNING"):
            layout = self._calculate(Attribute(name=Identifier("numbers"), data_type=data_type))
        self._assert_layout(layout)

    def test_map_composite_value_traverses_fields_for_array_and_string_config(self) -> None:
        value = StructDataType(
            name=Identifier("Value"),
            source_kind=DataTypeSource.FRANCA,
            fields=(
                self._field("array", self._array(), {"SomeIpArrayLengthWidth": 2}),
                self._field("text", PrimitiveDataType.STRING, self._string_properties("utf16be", 0)),
            ),
        )
        data_type = MapDataType(
            name=Identifier("Values"),
            source_kind=DataTypeSource.FRANCA,
            key_type=PrimitiveDataType.UINT16,
            value_type=value,
        )
        self._assert_layout(
            self._calculate(Attribute(name=Identifier("values"), data_type=data_type)),
            vector=2,
            string=0,
            encoding=StringEncoding.UTF16,
        )

    def test_map_composite_key_and_value_traverse_string_fields(self) -> None:
        composite_types = (
            StructDataType(
                name=Identifier("KeyStruct"),
                source_kind=DataTypeSource.FRANCA,
                fields=(self._field("text", PrimitiveDataType.STRING, self._string_properties("utf16be", 2)),),
            ),
            UnionDataType(
                name=Identifier("ValueUnion"),
                source_kind=DataTypeSource.FRANCA,
                fields=(self._field("text", PrimitiveDataType.STRING, self._string_properties("utf16be", 2)),),
            ),
        )
        mappings = (
            MapDataType(
                name=Identifier("StructKeyMap"),
                source_kind=DataTypeSource.FRANCA,
                key_type=composite_types[0],
                value_type=PrimitiveDataType.UINT16,
            ),
            MapDataType(
                name=Identifier("UnionValueMap"),
                source_kind=DataTypeSource.FRANCA,
                key_type=PrimitiveDataType.UINT16,
                value_type=composite_types[1],
            ),
        )
        for mapping in mappings:
            with self.subTest(mapping=str(mapping.name)):
                self._assert_layout(
                    self._calculate(Attribute(name=Identifier("lookup"), data_type=mapping)),
                    string=2,
                    encoding=StringEncoding.UTF16,
                )

    def test_map_named_array_uses_its_declared_array_width(self) -> None:
        value = StructDataType(
            name="Value",
            source_kind=DataTypeSource.FRANCA,
            fields=(self._field("samples", self._array(), {"SomeIpArrayLengthWidth": 2}),),
        )
        outer = self._array(value, name="Outer", width=4)
        mapping = MapDataType(
            name="Lookup",
            source_kind=DataTypeSource.FRANCA,
            key_type=PrimitiveDataType.UINT16,
            value_type=outer,
        )
        self._assert_layout(self._calculate(Attribute(name=Identifier("lookup"), data_type=mapping)), vector=4)

    def test_both_string_map_uses_its_complete_type_configuration(self) -> None:
        data_type = MapDataType(
            name=Identifier("Texts"),
            source_kind=DataTypeSource.FRANCA,
            key_type=PrimitiveDataType.STRING,
            value_type=PrimitiveDataType.STRING,
            deployment_properties={"SomeIpArrayLengthWidth": 2, **self._string_properties("utf16be", 0)},
        )
        self._assert_layout(
            self._calculate(Attribute(name=Identifier("texts"), data_type=data_type)),
            string=0,
            encoding=StringEncoding.UTF16,
        )

    def test_direct_string_attribute_uses_member_configuration(self) -> None:
        for encoding, endian, expected in (
            ("utf8", "be", StringEncoding.UTF8),
            ("utf16le", "le", StringEncoding.UTF16),
            ("utf16be", "be", StringEncoding.UTF16),
            ("ucs2", "be", StringEncoding.UTF16),
        ):
            with self.subTest(encoding=encoding):
                attribute = Attribute(name=Identifier("text"), data_type=PrimitiveDataType.STRING)
                layout = self._calculate(
                    attribute, {"SomeIpAttributeEndianess": endian, **self._string_properties(encoding, 0)}
                )
                self._assert_layout(
                    layout,
                    byte_order=ByteOrder.LITTLE_ENDIAN if endian == "le" else ByteOrder.BIG_ENDIAN,
                    string=0,
                    encoding=expected,
                )

    def test_named_string_array_uses_named_configuration_for_attribute_and_field(self) -> None:
        named = self._array(
            PrimitiveDataType.STRING, name="Texts", width=2, properties=self._string_properties("utf16le", 0)
        )
        attribute = Attribute(name=Identifier("texts"), data_type=named)
        method = Method(name=SelectableIdentifier("call"), inputs=[self._field("texts", named)])
        self._assert_layout(
            self._calculate(attribute, {"SomeIpAttributeEndianess": "le"}),
            byte_order=ByteOrder.LITTLE_ENDIAN,
            vector=2,
            string=0,
            encoding=StringEncoding.UTF16,
        )
        self._assert_layout(
            self._calculate(method, {"SomeIpMethodEndianess": "le"}),
            byte_order=ByteOrder.LITTLE_ENDIAN,
            vector=2,
            string=0,
            encoding=StringEncoding.UTF16,
        )

    def test_inline_string_array_uses_declaration_owner_configuration(self) -> None:
        inline = self._array(PrimitiveDataType.STRING, width=4, properties=self._string_properties("utf16le", 4))
        properties = {"SomeIpArrayLengthWidth": 2, **self._string_properties("utf8", 0)}
        attribute = Attribute(name=Identifier("texts"), data_type=inline)
        method = Method(name=SelectableIdentifier("call"), inputs=[self._field("texts", inline, properties)])
        for member, member_properties in ((attribute, properties), (method, {})):
            with self.subTest(member=type(member).__name__):
                with self.assertNoLogs(_LOGGER, level="WARNING"):
                    layout = self._calculate(member, member_properties)
                self._assert_layout(layout, vector=2, string=0)

    def test_unresolved_attribute_and_parameter_types_are_rejected(self) -> None:
        references = (Identifier("Missing"), QualifiedName((Identifier("Demo"), Identifier("Missing"))))
        for reference in references:
            scenarios = (
                Attribute(name=Identifier("missing"), data_type=reference),
                Method(name=SelectableIdentifier("call"), inputs=[self._field("missing", reference)]),
                Broadcast(name=SelectableIdentifier("event"), outputs=[self._field("missing", reference)]),
            )
            for member in scenarios:
                with self.subTest(member=type(member).__name__, reference=str(reference)):
                    with self.assertRaisesRegex(ValueError, "Unsupported unresolved layout type reference"):
                        self._calculate(member)
                    self.assertEqual(ElementLayout._instances, {})

    def test_unresolved_composite_base_is_rejected(self) -> None:
        for composite_type in (StructDataType, UnionDataType):
            with self.subTest(composite=composite_type.__name__):
                data_type = composite_type(
                    name=Identifier("Derived"), source_kind=DataTypeSource.FRANCA, extends=Identifier("Missing")
                )
                with self.assertRaisesRegex(ValueError, "(?i)unresolved"):
                    self._calculate(Attribute(name=Identifier("payload"), data_type=data_type))
                self.assertEqual(ElementLayout._instances, {})

    def test_recursive_typedef_and_struct_graphs_raise_instead_of_recursing_forever(self) -> None:
        alias = TypedefDataType(
            name=Identifier("Alias"), source_kind=DataTypeSource.FRANCA, data_type=PrimitiveDataType.UINT32
        )
        field = self._field("self", PrimitiveDataType.UINT32)
        structure = StructDataType(name=Identifier("Recursive"), source_kind=DataTypeSource.FRANCA, fields=(field,))
        # Simulate a resolver introducing back references after valid construction.
        object.__setattr__(alias, "data_type", alias)
        object.__setattr__(field, "data_type", structure)
        for data_type in (alias, structure):
            with self.subTest(data_type=type(data_type).__name__):
                with self.assertRaisesRegex(ValueError, "Recursive type graphs"):
                    self._calculate(Attribute(name=Identifier("recursive"), data_type=data_type))
                self.assertEqual(ElementLayout._instances, {})

    def test_only_declared_members_are_calculated(self) -> None:
        declared = Attribute(name=Identifier("value"), data_type=PrimitiveDataType.UINT32)
        other = Attribute(name=Identifier("value"), data_type=PrimitiveDataType.UINT32)
        layouts = calculate_interface_layouts(self._service(declared))
        self.assertEqual(list(layouts), [declared.id])
        self.assertNotIn(other.id, layouts)
        self._assert_layout(layouts[declared.id])


if __name__ == "__main__":
    unittest.main()
