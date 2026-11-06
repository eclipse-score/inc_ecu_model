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

"""Verify union alternatives, inheritance and dependency failures."""

import unittest

from score.ecu_model.data_types.common import DataTypeSource
from score.ecu_model.data_types.composite import DataTypeField
from score.ecu_model.data_types.enum import EnumDataType, EnumValue
from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.data_types.union import UnionDataType
from score.ecu_model.model import ModelRegistry
from score.generators.src.datatypes.cpp_model import CppAlias, CppField, CppVariant
from score.generators.src.datatypes.datatype_utils import DatatypeUtils


class UnionTypeTest(unittest.TestCase):
    """Verify union alternatives, inheritance and dependency failures."""

    def setUp(self):
        """Isolate model objects registered during each test."""
        ModelRegistry.elements.clear()
        self.addCleanup(ModelRegistry.elements.clear)

    def test_union_preserves_order_aliases_and_duplicate_types(self):
        """Union aliases retain every alternative and include only direct dependencies."""
        count = TypedefDataType(
            name="Count",
            namespace="shared",
            source_kind=DataTypeSource.FRANCA,
            data_type=PrimitiveDataType.UINT16,
        )
        choice = UnionDataType(
            name="Choice",
            namespace="example",
            source_kind=DataTypeSource.FRANCA,
            fields=[
                DataTypeField(name="count", data_type=count),
                DataTypeField(name="raw", data_type=PrimitiveDataType.UINT16),
                DataTypeField(name="again", data_type=count),
                DataTypeField(name="text", data_type=PrimitiveDataType.STRING),
            ],
        )
        headers = []

        registry = DatatypeUtils.build_type_registry([choice, choice.model_copy(deep=True)], headers.append)

        self.assertEqual([header.path for header in headers], ["shared/Count.h", "example/Choice.h"])
        self.assertEqual(
            headers[-1].declaration,
            CppVariant("Choice", ("::shared::Count", "std::uint16_t", "::shared::Count", "std::string")),
        )
        self.assertEqual(headers[-1].includes, ("<cstdint>", "<string>", "<variant>", "shared/Count.h"))
        self.assertIs(registry.named_types[choice.fully_qualified_name].header_model, headers[-1])

    def test_nested_union_dependencies_are_available_to_structs_and_typedefs(self):
        """Named alternatives complete before owners without leaking transitive includes."""
        record = StructDataType(name="Record", namespace="shared", source_kind=DataTypeSource.FRANCA)
        mode = EnumDataType(
            name="Mode",
            namespace="shared",
            source_kind=DataTypeSource.FRANCA,
            values=[EnumValue(name="Ready", value=0)],
        )
        inner = UnionDataType(
            name="Inner",
            namespace="shared",
            source_kind=DataTypeSource.FRANCA,
            fields=[DataTypeField(name="record", data_type=record), DataTypeField(name="mode", data_type=mode)],
        )
        outer = UnionDataType(
            name="Outer",
            namespace="example",
            source_kind=DataTypeSource.FRANCA,
            fields=[
                DataTypeField(name="inner", data_type=inner),
                DataTypeField(name="flag", data_type=PrimitiveDataType.BOOL),
            ],
        )
        alias = TypedefDataType(name="Public", namespace="example", source_kind=DataTypeSource.FRANCA, data_type=outer)
        envelope = StructDataType(
            name="Envelope",
            namespace="example",
            source_kind=DataTypeSource.FRANCA,
            fields=[DataTypeField(name="choice", data_type=outer)],
        )
        headers = []

        DatatypeUtils.build_type_registry([alias, envelope, inner], headers.append)

        self.assertEqual(
            [header.path for header in headers],
            [
                "shared/Record.h",
                "shared/Mode.h",
                "shared/Inner.h",
                "example/Outer.h",
                "example/Public.h",
                "example/Envelope.h",
            ],
        )
        self.assertEqual(headers[2].declaration, CppVariant("Inner", ("::shared::Record", "::shared::Mode")))
        self.assertEqual(headers[2].includes, ("<variant>", "shared/Mode.h", "shared/Record.h"))
        self.assertEqual(headers[3].declaration, CppVariant("Outer", ("::shared::Inner", "bool")))
        self.assertEqual(headers[3].includes, ("<variant>", "shared/Inner.h"))
        self.assertEqual(headers[4].declaration, CppAlias("Public", "::example::Outer"))
        self.assertEqual(headers[4].includes, ("example/Outer.h",))
        self.assertEqual(
            headers[5].declaration.fields, (CppField("choice", "::example::Outer", "choice_generated_type"),)
        )
        self.assertEqual(headers[5].includes, ("example/Outer.h",))

    def test_union_inheritance_reuses_cached_alternatives_and_includes(self):
        """Derived variants flatten local, parent and ancestor types without parent includes."""
        count = TypedefDataType(
            name="Count",
            namespace="shared",
            source_kind=DataTypeSource.FRANCA,
            data_type=PrimitiveDataType.UINT16,
        )
        nested = UnionDataType(
            name="Nested",
            namespace="shared",
            source_kind=DataTypeSource.FRANCA,
            fields=[DataTypeField(name="byte", data_type=PrimitiveDataType.UINT8)],
        )
        root = UnionDataType(
            name="Root",
            namespace="base",
            source_kind=DataTypeSource.FRANCA,
            fields=[
                DataTypeField(name="value", data_type=count),
                DataTypeField(name="nested", data_type=nested),
                DataTypeField(name="flag", data_type=PrimitiveDataType.BOOL),
            ],
        )
        middle = UnionDataType(
            name="Middle",
            namespace="derived",
            source_kind=DataTypeSource.FRANCA,
            extends=root,
            fields=[DataTypeField(name="value", data_type=PrimitiveDataType.STRING)],
        )
        leaf = UnionDataType(
            name="Leaf",
            namespace="example",
            source_kind=DataTypeSource.FRANCA,
            extends=middle,
            fields=[DataTypeField(name="flag", data_type=PrimitiveDataType.BOOL)],
        )
        inherited_only = UnionDataType(
            name="InheritedOnly",
            namespace="example",
            source_kind=DataTypeSource.FRANCA,
            extends=leaf,
        )
        original_model = inherited_only.model_dump()
        headers = []

        registry = DatatypeUtils.build_type_registry(
            [inherited_only, leaf, middle, root, inherited_only.model_copy(deep=True)],
            headers.append,
        )

        self.assertEqual(
            [header.path for header in headers],
            [
                "shared/Count.h",
                "shared/Nested.h",
                "base/Root.h",
                "derived/Middle.h",
                "example/Leaf.h",
                "example/InheritedOnly.h",
            ],
        )
        self.assertEqual(headers[2].declaration, CppVariant("Root", ("::shared::Count", "::shared::Nested", "bool")))
        self.assertEqual(
            headers[3].declaration, CppVariant("Middle", ("std::string", "::shared::Count", "::shared::Nested", "bool"))
        )
        self.assertEqual(
            headers[4].declaration,
            CppVariant("Leaf", ("bool", "std::string", "::shared::Count", "::shared::Nested", "bool")),
        )
        self.assertEqual(headers[5].declaration, CppVariant("InheritedOnly", headers[4].declaration.alternatives))
        for header in headers[3:]:
            self.assertEqual(header.includes, ("<string>", "<variant>", "shared/Count.h", "shared/Nested.h"))
        self.assertIs(registry.named_types[root.fully_qualified_name].header_model, headers[2])
        self.assertEqual(inherited_only.model_dump(), original_model)

    def test_union_inheritance_rejects_unresolved_parents_and_cycles(self):
        """Parent edges participate in the existing active-path dependency checks."""
        root = UnionDataType(name="Root", source_kind=DataTypeSource.FRANCA)
        child = UnionDataType(name="Child", source_kind=DataTypeSource.FRANCA, extends=root)
        alias = TypedefDataType(name="Alias", source_kind=DataTypeSource.FRANCA, data_type=root)
        holder = UnionDataType(
            name="Holder",
            source_kind=DataTypeSource.FRANCA,
            fields=[DataTypeField(name="alias", data_type=alias)],
        )
        for parent, message in (
            (root, "Cyclic datatype dependency detected: Root -> Root"),
            (child, "Cyclic datatype dependency detected: Root -> Child -> Root"),
            (holder, "Cyclic datatype dependency detected: Root -> Holder -> Alias -> Root"),
            (Identifier("Missing"), "Unresolved datatype reference"),
            (QualifiedName((Identifier("shared"), Identifier("Missing"))), "Unresolved datatype reference"),
        ):
            with self.subTest(message=message, parent=parent):
                malformed = root.model_copy(update={"extends": parent})
                headers = []
                with self.assertRaisesRegex(ValueError, message):
                    DatatypeUtils.build_type_registry([malformed], headers.append)
                self.assertEqual(headers, [])

    def test_union_rejects_empty_and_unnamed_declarations(self):
        """Unsupported union declarations never emit their own header."""
        empty_parent = UnionDataType(name="Empty", source_kind=DataTypeSource.FRANCA)
        choice = UnionDataType(
            name="Choice",
            source_kind=DataTypeSource.FRANCA,
            fields=[DataTypeField(name="flag", data_type=PrimitiveDataType.BOOL)],
        )
        for datatype, error, message in (
            (choice.model_copy(update={"fields": ()}), ValueError, "at least one alternative"),
            (choice.model_copy(update={"extends": empty_parent}), ValueError, "at least one alternative"),
            (choice.model_copy(update={"name": None}), ValueError, "Unions require a declared name"),
        ):
            with self.subTest(message=message):
                headers = []
                with self.assertRaisesRegex(error, message):
                    DatatypeUtils.build_type_registry([datatype], headers.append)
                self.assertEqual(headers, [])

    def test_union_rejects_unresolved_alternatives_and_dependency_cycles(self):
        """The shared traversal diagnoses references and union/typedef/struct cycles."""
        choice = UnionDataType(name="Choice", source_kind=DataTypeSource.FRANCA)
        alias = TypedefDataType(name="Alias", source_kind=DataTypeSource.FRANCA, data_type=choice)
        record = StructDataType(
            name="Record",
            source_kind=DataTypeSource.FRANCA,
            fields=[DataTypeField(name="choice", data_type=choice)],
        )
        other = UnionDataType(
            name="Other",
            source_kind=DataTypeSource.FRANCA,
            fields=[DataTypeField(name="choice", data_type=choice)],
        )
        for target in (
            choice,
            alias,
            record,
            other,
            Identifier("Missing"),
            QualifiedName((Identifier("shared"), Identifier("Missing"))),
        ):
            malformed = choice.model_copy(update={"fields": (DataTypeField(name="value", data_type=target),)})
            message = (
                "Unresolved datatype reference"
                if isinstance(target, (Identifier, QualifiedName))
                else "Cyclic datatype dependency detected: Choice ->"
            )
            with self.subTest(target=target):
                headers = []
                with self.assertRaisesRegex(ValueError, message):
                    DatatypeUtils.build_type_registry([malformed], headers.append)
                self.assertEqual(headers, [])


if __name__ == "__main__":
    unittest.main()
