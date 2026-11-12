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

"""Verify struct fields, inheritance, dependencies and rendering."""

import tempfile
import unittest
from pathlib import Path

from score.ecu_model.data_types.common import DataTypeSource
from score.ecu_model.data_types.composite import DataTypeField
from score.ecu_model.data_types.enum import EnumDataType, EnumValue
from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.model import ModelRegistry
from score.generators.src.datatypes.cpp_model import CppField, CppStruct
from score.generators.src.datatypes.datatype_generator import DatatypeGenerator
from score.generators.src.datatypes.datatype_utils import DatatypeUtils


class StructTypeTest(unittest.TestCase):
    """Verify struct fields, inheritance, dependencies and rendering."""

    def setUp(self):
        """Isolate model objects registered during each test."""
        ModelRegistry.elements.clear()
        self.addCleanup(ModelRegistry.elements.clear)

    def test_struct_preserves_field_order_and_renders_primitive_members(self):
        """Primitive fields use direct types with deduplicated definition includes."""
        record = StructDataType(
            name="Record",
            namespace="example",
            source_kind=DataTypeSource.FRANCA,
            fields=[
                DataTypeField(name="count", data_type=PrimitiveDataType.UINT16),
                DataTypeField(name="enabled", data_type=PrimitiveDataType.BOOL),
                DataTypeField(name="text", data_type=PrimitiveDataType.STRING),
            ],
        )
        original_model = record.model_dump()
        headers = []

        registry = DatatypeUtils.build_type_registry([record], headers.append)

        self.assertEqual(headers[0].includes, ("<cstdint>", "<string>"))
        self.assertEqual(
            headers[0].declaration,
            CppStruct(
                "Record",
                (
                    CppField("count", "std::uint16_t"),
                    CppField("enabled", "bool"),
                    CppField("text", "std::string"),
                ),
            ),
        )
        self.assertIs(registry.named_types["example.Record"].header_model, headers[0])
        self.assertEqual(record.model_dump(), original_model)
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)

            DatatypeGenerator().generate({"data_types": {record.id: record}}, output_dir)

            content = (output_dir / "example/Record.h").read_text(encoding="utf-8")
            self.assertIn(
                "struct Record {\n    std::uint16_t count;\n    bool enabled;\n    std::string text;\n};", content
            )

    def test_struct_named_fields_share_dependencies_and_render_usage_aliases(self):
        """Nested type references emit once before their owners and retain field order."""
        mode = EnumDataType(
            name="Mode",
            namespace="shared",
            source_kind=DataTypeSource.FRANCA,
            values=[EnumValue(name="Idle", value=0)],
        )
        child = StructDataType(
            name="Child",
            namespace="shared",
            source_kind=DataTypeSource.FRANCA,
            fields=[DataTypeField(name="mode", data_type=mode)],
        )
        child_alias = TypedefDataType(
            name="ChildAlias",
            namespace="example",
            source_kind=DataTypeSource.FRANCA,
            data_type=child,
        )
        parent = StructDataType(
            name="Parent",
            namespace="example",
            source_kind=DataTypeSource.FRANCA,
            fields=[
                DataTypeField(name="first", data_type=child_alias),
                DataTypeField(name="second", data_type=child),
                DataTypeField(name="third", data_type=child),
                DataTypeField(name="mode", data_type=mode),
            ],
        )
        original_model = parent.model_dump()
        for selected in ([parent, child.model_copy(deep=True), mode], [mode, child, child_alias, parent]):
            with self.subTest(order=[datatype.name for datatype in selected]):
                headers = []

                registry = DatatypeUtils.build_type_registry(selected, headers.append)

                self.assertEqual(
                    [header.path for header in headers],
                    [
                        "shared/Mode.h",
                        "shared/Child.h",
                        "example/ChildAlias.h",
                        "example/Parent.h",
                    ],
                )
                self.assertEqual(headers[-1].includes, ("example/ChildAlias.h", "shared/Child.h", "shared/Mode.h"))
                self.assertEqual(
                    headers[-1].declaration.fields,
                    (
                        CppField("first", "::example::ChildAlias", "first_generated_type"),
                        CppField("second", "::shared::Child", "second_generated_type"),
                        CppField("third", "::shared::Child", "third_generated_type"),
                        CppField("mode", "::shared::Mode", "mode_generated_type"),
                    ),
                )
                self.assertIs(registry.named_types["example.Parent"].header_model, headers[-1])
                self.assertEqual(parent.model_dump(), original_model)

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)

            DatatypeGenerator().generate({"data_types": {parent.id: parent}}, output_dir)

            content = (output_dir / "example/Parent.h").read_text(encoding="utf-8")
            self.assertIn("    using first_generated_type = ::example::ChildAlias;", content)
            self.assertIn("    using mode_generated_type = ::shared::Mode;", content)
            self.assertIn("    first_generated_type first;", content)
            self.assertEqual(content.count('#include "shared/Child.h"'), 1)
            self.assertEqual(len(list(output_dir.rglob("*.h"))), 4)

    def test_struct_inheritance_flattens_fields_and_reuses_parent_headers(self):
        """Local fields precede cached ancestors, preserving cross-namespace type dependencies."""
        count = TypedefDataType(
            name="Count", namespace="shared", source_kind=DataTypeSource.FRANCA, data_type=PrimitiveDataType.UINT16
        )
        mode = EnumDataType(
            name="Mode",
            namespace="shared",
            source_kind=DataTypeSource.FRANCA,
            values=[EnumValue(name="Idle", value=0)],
        )
        ancestor = StructDataType(
            name="Root",
            namespace="base",
            source_kind=DataTypeSource.FRANCA,
            fields=[
                DataTypeField(name="count", data_type=count),
                DataTypeField(name="text", data_type=PrimitiveDataType.STRING),
            ],
        )
        parent = StructDataType(
            name="Middle",
            namespace="base",
            source_kind=DataTypeSource.FRANCA,
            extends=ancestor,
            fields=[DataTypeField(name="mode", data_type=mode)],
        )
        derived = StructDataType(
            name="Record",
            namespace="app",
            source_kind=DataTypeSource.FRANCA,
            extends=parent,
            fields=[
                DataTypeField(name="enabled", data_type=PrimitiveDataType.BOOL),
                DataTypeField(name="other", data_type=count),
            ],
        )
        original_model = derived.model_dump()
        headers = []

        registry = DatatypeUtils.build_type_registry([derived, parent.model_copy(deep=True), ancestor], headers.append)

        self.assertEqual(
            [header.path for header in headers],
            [
                "shared/Count.h",
                "base/Root.h",
                "shared/Mode.h",
                "base/Middle.h",
                "app/Record.h",
            ],
        )
        self.assertEqual(
            headers[-1].declaration,
            CppStruct(
                "Record",
                (
                    CppField("enabled", "bool"),
                    CppField("other", "::shared::Count", "other_generated_type"),
                    CppField("mode", "::shared::Mode", "mode_generated_type"),
                    CppField("count", "::shared::Count", "count_generated_type"),
                    CppField("text", "std::string"),
                ),
            ),
        )
        self.assertEqual(headers[-1].includes, ("<string>", "shared/Count.h", "shared/Mode.h"))
        self.assertIs(registry.named_types["app.Record"].header_model, headers[-1])
        self.assertIs(headers[-1].declaration.fields[2], headers[-2].declaration.fields[0])
        self.assertIs(headers[-1].declaration.fields[3], headers[1].declaration.fields[0])
        self.assertEqual(derived.model_dump(), original_model)

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)

            DatatypeGenerator().generate({"data_types": {derived.id: derived}}, output_dir)

            content = (output_dir / "app/Record.h").read_text(encoding="utf-8")
            self.assertIn("struct Record {", content)
            self.assertIn("    mode_generated_type mode;", content)
            self.assertIn("    count_generated_type count;", content)
            self.assertIn("    std::string text;", content)
            self.assertNotIn("base/Root.h", content)
            self.assertNotIn("base/Middle.h", content)
            self.assertEqual(len(list(output_dir.rglob("*.h"))), 5)

    def test_struct_without_local_fields_preserves_inherited_fields_or_remains_empty(self):
        """An empty local declaration may inherit all fields, including an empty field set."""
        for parent_fields in ([], [DataTypeField(name="text", data_type=PrimitiveDataType.STRING)]):
            with self.subTest(parent_fields=parent_fields):
                parent = StructDataType(name="Parent", source_kind=DataTypeSource.FRANCA, fields=parent_fields)
                derived = StructDataType(name="Derived", source_kind=DataTypeSource.FRANCA, extends=parent)
                headers = []

                DatatypeUtils.build_type_registry([derived], headers.append)

                self.assertEqual([header.path for header in headers], ["Parent.h", "Derived.h"])
                self.assertEqual(headers[1].declaration.fields, headers[0].declaration.fields)
                self.assertEqual(headers[1].includes, headers[0].includes)

    def test_struct_inherited_field_name_collisions_are_rejected(self):
        """Local fields never overwrite names from a parent or a more distant ancestor."""
        for inherited_from_ancestor in (False, True):
            with self.subTest(inherited_from_ancestor=inherited_from_ancestor):
                ancestor = StructDataType(
                    name="Ancestor",
                    source_kind=DataTypeSource.FRANCA,
                    fields=[DataTypeField(name="count", data_type=PrimitiveDataType.UINT16)],
                )
                parent = ancestor
                expected_paths = ["Ancestor.h"]
                if inherited_from_ancestor:
                    parent = StructDataType(
                        name="Parent",
                        source_kind=DataTypeSource.FRANCA,
                        extends=ancestor,
                        fields=[DataTypeField(name="enabled", data_type=PrimitiveDataType.BOOL)],
                    )
                    expected_paths.append("Parent.h")
                derived = StructDataType(
                    name="Derived",
                    source_kind=DataTypeSource.FRANCA,
                    extends=parent,
                    fields=[DataTypeField(name="count", data_type=PrimitiveDataType.STRING)],
                )
                headers = []

                with self.assertRaisesRegex(ValueError, r"Duplicate struct field name: Derived\.count"):
                    DatatypeUtils.build_type_registry([derived], headers.append)

                self.assertEqual([header.path for header in headers], expected_paths)

    def test_struct_inheritance_cycles_fail_before_header_notification(self):
        """UUID traversal rejects direct, indirect, and mixed inheritance/field cycles."""
        for cycle in ("self", "inheritance", "field"):
            with self.subTest(cycle=cycle):
                first = StructDataType(name="First", source_kind=DataTypeSource.FRANCA)
                if cycle == "self":
                    parent = first
                    expected_chain = "First -> First"
                elif cycle == "inheritance":
                    parent = StructDataType(name="Second", source_kind=DataTypeSource.FRANCA, extends=first)
                    expected_chain = "First -> Second -> First"
                else:
                    parent = StructDataType(
                        name="Second",
                        source_kind=DataTypeSource.FRANCA,
                        fields=[DataTypeField(name="first", data_type=first)],
                    )
                    expected_chain = "First -> Second -> First"
                first = first.model_copy(update={"extends": parent})
                headers = []

                with self.assertRaisesRegex(ValueError, "Cyclic datatype dependency detected: " + expected_chain):
                    DatatypeUtils.build_type_registry([first], headers.append)

                self.assertEqual(headers, [])

    def test_struct_cycles_fail_before_header_notification(self):
        """By-value cycles cannot be broken by a struct reference or typedef."""
        for cycle in ("self", "mutual", "typedef"):
            with self.subTest(cycle=cycle):
                first = StructDataType(name="First", source_kind=DataTypeSource.FRANCA)
                if cycle == "self":
                    target = first
                    expected_chain = "First -> First"
                elif cycle == "mutual":
                    target = StructDataType(
                        name="Second",
                        source_kind=DataTypeSource.FRANCA,
                        fields=[DataTypeField(name="first", data_type=first)],
                    )
                    expected_chain = "First -> Second -> First"
                else:
                    target = TypedefDataType(name="Alias", source_kind=DataTypeSource.FRANCA, data_type=first)
                    expected_chain = "First -> Alias -> First"
                first.fields = (DataTypeField(name="next", data_type=target),)
                headers = []

                with self.assertRaisesRegex(ValueError, "Cyclic datatype dependency detected: " + expected_chain):
                    DatatypeUtils.build_type_registry([first], headers.append)

                self.assertEqual(headers, [])

    def test_struct_unresolved_references_fail_before_emission(self):
        """Field and parent references must already be resolved by the importer."""
        for reference in (Identifier("Missing"), QualifiedName((Identifier("shared"), Identifier("Missing")))):
            for dependency in (
                {"fields": [DataTypeField(name="value", data_type=reference)]},
                {"extends": reference},
            ):
                with self.subTest(reference=reference, dependency=dependency):
                    record = StructDataType(name="Record", source_kind=DataTypeSource.FRANCA, **dependency)
                    headers = []

                    with self.assertRaisesRegex(ValueError, "Unresolved datatype reference"):
                        DatatypeUtils.build_type_registry([record], headers.append)

                    self.assertEqual(headers, [])

    def test_struct_missing_name_is_rejected(self):
        """Struct declarations require a name for their generated header."""
        base = StructDataType(name="Base", source_kind=DataTypeSource.FRANCA)
        unnamed = base.model_copy(update={"name": None})
        with self.assertRaisesRegex(ValueError, "Structs require a declared name"):
            DatatypeUtils.build_type_registry([unnamed], lambda header: self.fail("Unexpected header"))


if __name__ == "__main__":
    unittest.main()
