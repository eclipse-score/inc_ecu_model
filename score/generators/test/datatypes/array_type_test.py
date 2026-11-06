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

"""Verify array lowering, deployment ownership and dependency failures."""

import unittest

from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.common import DataTypeSource
from score.ecu_model.data_types.composite import DataTypeField
from score.ecu_model.data_types.identifier import Identifier
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.data_types.union import UnionDataType
from score.ecu_model.model import ModelRegistry
from score.generators.src.datatypes.cpp_model import CppAlias, CppVariant
from score.generators.src.datatypes.datatype_utils import DatatypeUtils


class ArrayTypeTest(unittest.TestCase):
    """Exercise named and anonymous array generation through datatype lowering."""

    def setUp(self):
        """Isolate model objects registered during each test."""
        ModelRegistry.elements.clear()
        self.addCleanup(ModelRegistry.elements.clear)

    def test_array_dependencies_generate_before_their_owners(self):
        """Structs, aliases and unions reuse a completed named array header."""
        target = ArrayDataType(
            name="Items",
            source_kind=DataTypeSource.FRANCA,
            data_type=PrimitiveDataType.UINT8,
            dimension_min=7,
            dimension_max=7,
        )
        record = StructDataType(
            name="Record",
            source_kind=DataTypeSource.FRANCA,
            fields=[DataTypeField(name="value", data_type=target)],
        )
        alias = TypedefDataType(name="Alias", source_kind=DataTypeSource.FRANCA, data_type=target)
        choice = UnionDataType(
            name="Choice",
            source_kind=DataTypeSource.FRANCA,
            fields=[DataTypeField(name="items", data_type=target)],
        )
        for datatype in (target, record, alias, choice):
            with self.subTest(root=datatype.name):
                headers = []

                DatatypeUtils.build_type_registry([datatype], headers.append)

                self.assertEqual(headers[0].declaration, CppAlias("Items", "std::array<std::uint8_t, 7>"))
                self.assertEqual(headers[-1].path, datatype.name.as_str + ".h")

    def test_arrays_resolve_raw_bounds_and_deployment_without_mutating_models(self):
        """Explicit max wins; otherwise stored deployment supplies both bounds."""
        for minimum, maximum, properties, expression in (
            (None, 7, {}, "std::array<std::uint16_t, 7>"),
            (3, 7, {}, "std::vector<std::uint16_t>"),
            (0, 0, {}, "std::vector<std::uint16_t>"),
            (None, 7, {"SomeIpArrayMinLength": 3, "IpcArrayMinLength": 5}, "std::array<std::uint16_t, 7>"),
            (None, None, {"SomeIpArrayMinLength": 5, "SomeIpArrayMaxLength": 5}, "std::array<std::uint16_t, 5>"),
            (None, None, {"SomeIpArrayMinLength": 0, "SomeIpArrayMaxLength": 7}, "std::vector<std::uint16_t>"),
            (None, None, {"SomeIpArrayMinLength": 0, "SomeIpArrayMaxLength": 0}, "std::vector<std::uint16_t>"),
            (7, None, {"IpcArrayMinLength": 3, "IpcArrayMaxLength": 9}, "std::vector<std::uint16_t>"),
        ):
            with self.subTest(minimum=minimum, maximum=maximum, properties=properties):
                datatype = ArrayDataType(
                    name="Samples",
                    namespace="example",
                    source_kind=DataTypeSource.FRANCA,
                    data_type=PrimitiveDataType.UINT16,
                    dimension_min=minimum,
                    dimension_max=maximum,
                    deployment_properties=properties,
                )
                original_model = datatype.model_dump()
                headers = []

                registry = DatatypeUtils.build_type_registry([datatype, datatype], headers.append)

                self.assertEqual(len(headers), 1)
                self.assertEqual(headers[0].declaration, CppAlias("Samples", expression))
                self.assertEqual(
                    headers[0].includes,
                    ("<array>", "<cstdint>") if "std::array" in expression else ("<cstdint>", "<vector>"),
                )
                self.assertIs(registry.named_types["example.Samples"].header_model, headers[0])
                self.assertEqual(datatype.model_dump(), original_model)

    def test_array_protocol_bounds_agree_or_fail_with_diagnostic_fallback(self):
        """Applied defaults participate in conflicts; Diagnostic is a fallback only."""
        for properties, expression, failure in (
            (
                {
                    "SomeIpArrayMinLength": 3,
                    "SomeIpArrayMaxLength": 7,
                    "IpcArrayMinLength": 3,
                    "IpcArrayMaxLength": 7,
                    "PersistencyArrayMinLength": 3,
                    "PersistencyArrayMaxLength": 7,
                },
                "std::vector<std::uint16_t>",
                None,
            ),
            ({"DiagnosticArrayMinLength": 5, "DiagnosticArrayMaxLength": 5}, "std::array<std::uint16_t, 5>", None),
            (
                {
                    "SomeIpArrayMinLength": 3,
                    "SomeIpArrayMaxLength": 7,
                    "DiagnosticArrayMinLength": 5,
                    "DiagnosticArrayMaxLength": 5,
                },
                "std::vector<std::uint16_t>",
                None,
            ),
            ({"SomeIpArrayMinLength": 3, "IpcArrayMaxLength": 7}, "std::vector<std::uint16_t>", None),
            (
                {"SomeIpArrayMinLength": 3, "IpcArrayMinLength": 4, "SomeIpArrayMaxLength": 7},
                None,
                "Conflicting array MinLength",
            ),
            (
                {"SomeIpArrayMinLength": 3, "SomeIpArrayMaxLength": 7, "PersistencyArrayMaxLength": 9},
                None,
                "Conflicting array MaxLength",
            ),
            (
                {"SomeIpArrayMinLength": 0, "IpcArrayMinLength": 3, "SomeIpArrayMaxLength": 7},
                None,
                "Conflicting array MinLength",
            ),
            ({"SomeIpArrayMinLength": 0}, None, "Missing array bounds for example.Samples: max"),
            ({"SomeIpArrayMaxLength": 7}, None, "Missing array bounds for example.Samples: min"),
            ({"SomeIpArrayMinLength": -1, "SomeIpArrayMaxLength": 7}, None, "Invalid array bounds"),
            ({"SomeIpArrayMinLength": 8, "SomeIpArrayMaxLength": 7}, None, "Invalid array bounds"),
            ({"SomeIpArrayMinLength": True, "SomeIpArrayMaxLength": 7}, None, "expected integer"),
            ({"SomeIpArrayMinLength": "3", "SomeIpArrayMaxLength": 7}, None, "expected integer"),
        ):
            with self.subTest(properties=properties):
                datatype = ArrayDataType(
                    name="Samples",
                    namespace="example",
                    source_kind=DataTypeSource.FRANCA,
                    data_type=PrimitiveDataType.UINT16,
                    deployment_properties=properties,
                )
                original_model = datatype.model_dump()
                headers = []

                if failure:
                    with self.assertRaisesRegex(ValueError, failure):
                        DatatypeUtils.build_type_registry([datatype], headers.append)
                    self.assertEqual(headers, [])
                else:
                    DatatypeUtils.build_type_registry([datatype], headers.append)
                    self.assertEqual(headers[0].declaration, CppAlias("Samples", expression))
                self.assertEqual(datatype.model_dump(), original_model)

    def test_shared_inline_arrays_use_each_struct_field_deployment_in_either_order(self):
        """Shared UUID traversal never caches a field-specific array expression."""
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                inline = ArrayDataType(
                    is_inline=True,
                    source_kind=DataTypeSource.FRANCA,
                    data_type=PrimitiveDataType.UINT16,
                    deployment_properties={"SomeIpArrayMinLength": 9, "SomeIpArrayMaxLength": 9},
                )
                owners = [
                    StructDataType(
                        name=name,
                        namespace="example",
                        source_kind=DataTypeSource.FRANCA,
                        fields=[
                            DataTypeField(
                                name="samples",
                                data_type=inline,
                                deployment_properties={
                                    "SomeIpArrayMinLength": minimum,
                                    "SomeIpArrayMaxLength": maximum,
                                },
                            )
                        ],
                    )
                    for name, minimum, maximum in (("First", 3, 7), ("Second", 5, 5))
                ]
                if reverse:
                    owners.reverse()
                originals = [owner.model_dump() for owner in owners]
                headers = []

                registry = DatatypeUtils.build_type_registry(owners, headers.append)

                fields = {header.declaration.name: header.declaration.fields[0].cpp_type for header in headers}
                self.assertEqual(
                    fields, {"First": "std::vector<std::uint16_t>", "Second": "std::array<std::uint16_t, 5>"}
                )
                self.assertEqual(set(registry.named_types), {"example.First", "example.Second"})
                self.assertEqual([owner.model_dump() for owner in owners], originals)

    def test_named_array_reference_fields_cannot_fill_or_override_type_bounds(self):
        """Named arrays retain their own deployment regardless of reference field properties."""
        for properties, failure in (({"SomeIpArrayMinLength": 3, "SomeIpArrayMaxLength": 7}, False), ({}, True)):
            with self.subTest(properties=properties):
                array = ArrayDataType(
                    name="Samples",
                    namespace="example",
                    source_kind=DataTypeSource.FRANCA,
                    data_type=PrimitiveDataType.UINT16,
                    deployment_properties=properties,
                )
                owner = StructDataType(
                    name="Record",
                    namespace="example",
                    source_kind=DataTypeSource.FRANCA,
                    fields=[
                        DataTypeField(
                            name="samples",
                            data_type=array,
                            deployment_properties={"SomeIpArrayMinLength": 5, "SomeIpArrayMaxLength": 5},
                        )
                    ],
                )
                original_model = owner.model_dump()
                headers = []

                if failure:
                    with self.assertRaisesRegex(ValueError, "Missing array bounds for example.Samples: min, max"):
                        DatatypeUtils.build_type_registry([owner], headers.append)
                    self.assertEqual(headers, [])
                else:
                    DatatypeUtils.build_type_registry([owner], headers.append)
                    self.assertEqual(headers[0].declaration, CppAlias("Samples", "std::vector<std::uint16_t>"))
                    self.assertEqual(headers[-1].declaration.fields[0].cpp_type, "::example::Samples")
                self.assertEqual(owner.model_dump(), original_model)

    def test_empty_inline_field_deployment_reports_owner_without_array_property_fallback(self):
        """An empty field dictionary must not select the anonymous object's own properties."""
        for owner_type in (StructDataType, UnionDataType):
            with self.subTest(owner_type=owner_type.__name__):
                inline = ArrayDataType(
                    is_inline=True,
                    source_kind=DataTypeSource.FRANCA,
                    data_type=PrimitiveDataType.UINT16,
                    deployment_properties={"SomeIpArrayMinLength": 5, "SomeIpArrayMaxLength": 5},
                )
                owner = owner_type(
                    name="Record",
                    namespace="example",
                    source_kind=DataTypeSource.FRANCA,
                    fields=[DataTypeField(name="samples", data_type=inline)],
                )
                original_model = owner.model_dump()

                with self.assertRaisesRegex(ValueError, "Missing array bounds for example.Record.samples: min, max"):
                    DatatypeUtils.build_type_registry([owner], lambda header: self.fail("Unexpected header"))

                self.assertEqual(owner.model_dump(), original_model)

    def test_inline_arrays_reject_typedef_targets_and_anonymous_elements(self):
        """Do not invent deployment semantics for context-free inline array targets."""
        inline = ArrayDataType(
            is_inline=True,
            source_kind=DataTypeSource.FRANCA,
            data_type=PrimitiveDataType.UINT16,
            deployment_properties={"SomeIpArrayMinLength": 7, "SomeIpArrayMaxLength": 7},
        )
        owners = [
            TypedefDataType(
                name="PublicRows",
                namespace="example",
                source_kind=DataTypeSource.FRANCA,
                data_type=ArrayDataType(
                    is_inline=True,
                    source_kind=DataTypeSource.FRANCA,
                    data_type=ArrayDataType(
                        name="Row",
                        source_kind=DataTypeSource.FRANCA,
                        data_type=PrimitiveDataType.UINT16,
                        dimension_min=7,
                        dimension_max=7,
                    ),
                ),
            ),
            ArrayDataType(
                name="Rows",
                namespace="example",
                source_kind=DataTypeSource.FRANCA,
                data_type=inline,
                dimension_min=5,
                dimension_max=5,
            ),
        ]
        for owner_type in (StructDataType, UnionDataType):
            owners.append(
                owner_type(
                    name="Grid",
                    namespace="example",
                    source_kind=DataTypeSource.FRANCA,
                    fields=[
                        DataTypeField(
                            name="rows",
                            data_type=ArrayDataType(
                                is_inline=True,
                                source_kind=DataTypeSource.FRANCA,
                                data_type=inline,
                            ),
                            deployment_properties={"SomeIpArrayMinLength": 5, "SomeIpArrayMaxLength": 5},
                        )
                    ],
                )
            )
        for owner in owners:
            with self.subTest(owner=owner.name):
                original_model = owner.model_dump()
                with self.assertRaisesRegex(NotImplementedError, "Inline array"):
                    DatatypeUtils.build_type_registry([owner], lambda header: self.fail("Unexpected header"))
                self.assertEqual(owner.model_dump(), original_model)

    def test_nested_inline_array_references_named_array_with_independent_bounds(self):
        """The outer field controls row count, not the named row's element count."""
        row = ArrayDataType(
            name="Row",
            namespace="example.Shared",
            source_kind=DataTypeSource.FRANCA,
            data_type=PrimitiveDataType.UINT16,
            deployment_properties={"SomeIpArrayMinLength": 7, "SomeIpArrayMaxLength": 7},
        )
        grid = StructDataType(
            name="Grid",
            namespace="example",
            source_kind=DataTypeSource.FRANCA,
            fields=[
                DataTypeField(
                    name="rows",
                    data_type=ArrayDataType(is_inline=True, source_kind=DataTypeSource.FRANCA, data_type=row),
                    deployment_properties={"SomeIpArrayMinLength": 5, "SomeIpArrayMaxLength": 5},
                )
            ],
        )
        original_model = grid.model_dump()
        headers = []

        DatatypeUtils.build_type_registry([grid, row], headers.append)

        self.assertEqual([header.path for header in headers], ["example/Shared/Row.h", "example/Grid.h"])
        self.assertEqual(headers[0].declaration, CppAlias("Row", "std::array<std::uint16_t, 7>"))
        self.assertEqual(headers[1].declaration.fields[0].cpp_type, "std::array<::example::Shared::Row, 5>")
        self.assertEqual(headers[1].includes, ("<array>", "example/Shared/Row.h"))
        self.assertEqual(grid.model_dump(), original_model)

    def test_nested_named_arrays_resolve_independent_bounds_and_direct_includes(self):
        """Each named array uses its own deployment and emits before its dependents."""
        row = ArrayDataType(
            name="Row",
            namespace="example.Shared",
            source_kind=DataTypeSource.FRANCA,
            data_type=PrimitiveDataType.UINT16,
            deployment_properties={"SomeIpArrayMinLength": 7, "SomeIpArrayMaxLength": 7},
        )
        rows = ArrayDataType(
            name="Rows",
            namespace="example",
            source_kind=DataTypeSource.FRANCA,
            data_type=row,
            deployment_properties={"SomeIpArrayMinLength": 5, "SomeIpArrayMaxLength": 5},
        )
        original_model = rows.model_dump()
        headers = []

        DatatypeUtils.build_type_registry([rows, row, rows], headers.append)

        self.assertEqual([header.path for header in headers], ["example/Shared/Row.h", "example/Rows.h"])
        self.assertEqual(headers[0].declaration, CppAlias("Row", "std::array<std::uint16_t, 7>"))
        self.assertEqual(headers[0].includes, ("<array>", "<cstdint>"))
        self.assertEqual(headers[1].declaration, CppAlias("Rows", "std::array<::example::Shared::Row, 5>"))
        self.assertEqual(headers[1].includes, ("<array>", "example/Shared/Row.h"))
        self.assertEqual(rows.model_dump(), original_model)

    def test_union_array_alternatives_preserve_repeated_dynamic_types(self):
        """Array support does not introduce demo canonical duplicate-type rejection."""
        choice = UnionDataType(
            name="Choice",
            source_kind=DataTypeSource.FRANCA,
            fields=[
                DataTypeField(
                    name=name,
                    data_type=ArrayDataType(
                        is_inline=True, source_kind=DataTypeSource.FRANCA, data_type=PrimitiveDataType.UINT16
                    ),
                    deployment_properties={"SomeIpArrayMinLength": minimum, "SomeIpArrayMaxLength": maximum},
                )
                for name, minimum, maximum in (("first", 0, 7), ("second", 3, 9))
            ],
        )
        headers = []

        DatatypeUtils.build_type_registry([choice], headers.append)

        self.assertEqual(
            headers[0].declaration, CppVariant("Choice", ("std::vector<std::uint16_t>", "std::vector<std::uint16_t>"))
        )
        self.assertEqual(headers[0].includes, ("<cstdint>", "<variant>", "<vector>"))

    def test_arrays_reject_invalid_bounds_unresolved_elements_and_cycles(self):
        """Named and anonymous arrays keep dependency and bound failures explicit."""
        for inline in (False, True):
            for minimum, maximum, message in (
                (None, None, "Missing array bounds"),
                (7, None, "Missing array bounds"),
                (-1, -1, "Invalid array bounds"),
                (8, 7, "Invalid array bounds"),
            ):
                with self.subTest(inline=inline, minimum=minimum, maximum=maximum):
                    array = ArrayDataType(
                        name=None if inline else "Samples",
                        is_inline=inline,
                        source_kind=DataTypeSource.FRANCA,
                        data_type=PrimitiveDataType.UINT16,
                    ).model_copy(update={"dimension_min": minimum, "dimension_max": maximum})
                    owner = StructDataType(
                        name="Record",
                        source_kind=DataTypeSource.FRANCA,
                        fields=[DataTypeField(name="samples", data_type=array)],
                    )
                    with self.assertRaisesRegex(ValueError, message):
                        DatatypeUtils.build_type_registry([owner], lambda header: self.fail("Unexpected header"))
            array = ArrayDataType(
                name=None if inline else "Samples",
                is_inline=inline,
                source_kind=DataTypeSource.FRANCA,
                data_type=PrimitiveDataType.UINT16,
                dimension_min=7,
                dimension_max=7,
            )
            for target, message in (
                ("Missing", "Unresolved datatype reference"),
                (array, "Cyclic datatype dependency detected"),
            ):
                with self.subTest(inline=inline, target=target):
                    malformed = array.model_copy(
                        update={"data_type": Identifier(target) if isinstance(target, str) else target}
                    )
                    with self.assertRaisesRegex(ValueError, message):
                        DatatypeUtils.build_type_registry([malformed], lambda header: self.fail("Unexpected header"))


if __name__ == "__main__":
    unittest.main()
