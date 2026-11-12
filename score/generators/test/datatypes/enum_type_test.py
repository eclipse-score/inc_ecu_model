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

"""Verify enum storage, literals, inheritance and rendering."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from score.ecu_model.data_types.common import DataTypeSource
from score.ecu_model.data_types.enum import EnumDataType, EnumValue
from score.ecu_model.data_types.identifier import Identifier
from score.ecu_model.model import ModelRegistry
from score.generators.src.datatypes.cpp_model import CppEnum, CppEnumerator
from score.generators.src.datatypes.datatype_generator import DatatypeGenerator
from score.generators.src.datatypes.datatype_utils import DatatypeUtils


class EnumTypeTest(unittest.TestCase):
    """Verify enum storage, literals, inheritance and rendering."""

    def setUp(self):
        """Isolate model objects registered during each test."""
        ModelRegistry.elements.clear()
        self.addCleanup(ModelRegistry.elements.clear)

    def test_enum_underlying_type_uses_each_supported_size_and_signedness(self):
        """Enums use model storage metadata and preserve its boundary values."""
        for size in (8, 16, 32, 64):
            for signed in (False, True):
                with self.subTest(size=size, signed=signed):
                    minimum = -(1 << (size - 1)) if signed else 0
                    maximum = (1 << (size - int(signed))) - 1
                    datatype = EnumDataType(
                        name="Mode",
                        source_kind=DataTypeSource.FRANCA,
                        size=size,
                        signed=signed,
                        deployment_properties={"EnumBackingType": "Int8", "SomeIpEnumWidth": 1},
                        values=(EnumValue(name="Minimum", value=minimum), EnumValue(name="Maximum", value=maximum)),
                    )
                    original_model = datatype.model_dump()
                    headers = []

                    registry = DatatypeUtils.build_type_registry(
                        [datatype, datatype.model_copy(deep=True)], headers.append
                    )

                    self.assertEqual(len(headers), 1)
                    cpp_integer_type = "int" if signed else "uint"
                    self.assertEqual(
                        headers[0].declaration,
                        CppEnum(
                            "Mode",
                            f"std::{cpp_integer_type}{size}_t",
                            (
                                CppEnumerator("Minimum", minimum),
                                CppEnumerator("Maximum", maximum),
                            ),
                        ),
                    )
                    self.assertEqual(headers[0].includes, ("<cstdint>",))
                    self.assertEqual(registry.named_types["Mode"].required_includes, ("Mode.h",))
                    self.assertEqual(datatype.model_dump(), original_model)

    def test_enum_header_preserves_numeric_aliases_and_emits_no_comparison_helpers(self):
        """Rendering emits ordered literals, including duplicate numeric values."""
        enumeration = EnumDataType(
            name="Mode",
            namespace="example",
            source_kind=DataTypeSource.FRANCA,
            values=(
                EnumValue(name="Busy", value=16),
                EnumValue(name="Idle", value=0),
                EnumValue(name="Default", value=0),
            ),
        )
        self.assertEqual(ModelRegistry.elements, {enumeration.id: enumeration})
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)

            DatatypeGenerator().generate({"data_types": dict(ModelRegistry.elements)}, output_dir)

            content = (output_dir / "example/Mode.h").read_text(encoding="utf-8")
            self.assertIn("#include <cstdint>\n", content)
            self.assertIn(
                "enum class Mode : std::uint32_t {\n    Busy = 16,\n    Idle = 0,\n    Default = 0\n};\n",
                content,
            )
            self.assertNotIn("operator", content)
            digest = hashlib.sha256(b"example/Mode.h").hexdigest()[:24].upper()
            self.assertTrue(content.endswith(f"#endif  // EXAMPLE_MODE_H_{digest}_\n"))
            self.assertEqual(len(list(output_dir.rglob("*.h"))), 1)

    def test_enum_out_of_range_values_fail_before_notification(self):
        """Enum values outside the declared storage range are rejected without emitting a header."""
        for size in (8, 16, 32, 64):
            for signed in (False, True):
                minimum = -(1 << (size - 1)) if signed else 0
                maximum = (1 << (size - int(signed))) - 1
                for value in (minimum - 1, maximum + 1):
                    with self.subTest(size=size, signed=signed, value=value):
                        enumeration = EnumDataType(
                            name="Mode",
                            source_kind=DataTypeSource.FRANCA,
                            size=size,
                            signed=signed,
                            values=(EnumValue(name="Invalid", value=value),),
                        )
                        headers = []

                        with self.assertRaisesRegex(ValueError, "Enum value outside.*Mode.Invalid"):
                            DatatypeUtils.build_type_registry([enumeration], headers.append)

                        self.assertEqual(headers, [])

    def test_enum_without_literals_or_numeric_values_is_rejected(self):
        """Generation neither invents literals nor resolves implicit numbering."""
        for values, message in (
            ((), "at least one enumerator"),
            ((EnumValue(name="Pending"),), r"Missing numeric value for enum literal: Mode\.Pending"),
        ):
            with self.subTest(message=message):
                enumeration = EnumDataType(name="Mode", source_kind=DataTypeSource.FRANCA, values=values)
                headers = []

                with self.assertRaisesRegex(ValueError, message):
                    DatatypeUtils.build_type_registry([enumeration], headers.append)

                self.assertEqual(headers, [])

    def test_enum_without_name_or_supported_storage_is_rejected(self):
        """Enums need a name and one of the supported fixed-width storage types."""
        for name, size, message in ((None, 8, "declared name"), ("Mode", 24, "Unsupported enum storage size")):
            with self.subTest(name=name, size=size):
                enumeration = EnumDataType(
                    name="Mode",
                    size=size,
                    source_kind=DataTypeSource.FRANCA,
                    values=(EnumValue(name="Idle", value=0),),
                ).model_copy(update={"name": Identifier(name) if name is not None else None})
                headers = []

                with self.assertRaisesRegex(ValueError, message):
                    DatatypeUtils.build_type_registry([enumeration], headers.append)

                self.assertEqual(headers, [])

    def test_enum_inheritance_flattens_ancestors_in_source_order_without_mutation(self):
        """Ancestors emit once before the derived enum, whose members remain independently defined."""
        ancestor = EnumDataType(
            name="Ancestor",
            source_kind=DataTypeSource.FRANCA,
            size=16,
            values=[EnumValue(name="AncestorValue", value=2)],
        )
        base = EnumDataType(
            name="Base",
            source_kind=DataTypeSource.FRANCA,
            size=16,
            extends=ancestor,
            values=[EnumValue(name="BaseValue", value=1)],
        )
        derived = EnumDataType(
            name="Derived",
            source_kind=DataTypeSource.FRANCA,
            size=8,
            extends=base,
            values=[EnumValue(name="Active", value=3)],
        )
        original_model = derived.model_dump()
        headers = []

        registry = DatatypeUtils.build_type_registry([derived, base.model_copy(deep=True), ancestor], headers.append)

        self.assertEqual([header.path for header in headers], ["Ancestor.h", "Base.h", "Derived.h"])
        self.assertIs(registry.named_types["Ancestor"].header_model, headers[0])
        self.assertIs(registry.named_types["Base"].header_model, headers[1])
        self.assertIs(registry.named_types["Derived"].header_model, headers[2])
        self.assertIs(headers[1].declaration.values[1], headers[0].declaration.values[0])
        self.assertIs(headers[2].declaration.values[1], headers[1].declaration.values[0])
        self.assertIs(headers[2].declaration.values[2], headers[0].declaration.values[0])
        self.assertEqual(
            [(member.name, member.value) for member in headers[-1].declaration.values],
            [("Active", 3), ("BaseValue", 1), ("AncestorValue", 2)],
        )
        self.assertEqual(headers[-1].declaration.underlying_type, "std::uint8_t")
        self.assertEqual(headers[-1].includes, ("<cstdint>",))
        self.assertEqual(derived.model_dump(), original_model)

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)

            DatatypeGenerator().generate({"data_types": {derived.id: derived}}, output_dir)

            self.assertEqual(
                sorted(path.name for path in output_dir.glob("*.h")), ["Ancestor.h", "Base.h", "Derived.h"]
            )
            content = (output_dir / "Derived.h").read_text(encoding="utf-8")
            self.assertIn(
                "enum class Derived : std::uint8_t {\n    Active = 3,\n    BaseValue = 1,\n    AncestorValue = 2\n};\n",
                content,
            )
            self.assertNotIn('#include "Base.h"', content)
            self.assertNotIn('#include "Ancestor.h"', content)
            self.assertEqual(derived.model_dump(), original_model)

    def test_enum_with_only_inherited_members_has_no_parent_header_dependency(self):
        """A derived enum may have no local members and remains a distinct C++ type."""
        base = EnumDataType(
            name="Base",
            namespace="shared",
            source_kind=DataTypeSource.FRANCA,
            values=[EnumValue(name="Idle", value=7)],
        )
        derived = EnumDataType(
            name="Derived", namespace="example", source_kind=DataTypeSource.FRANCA, extends=base, size=8
        )
        headers = []

        registry = DatatypeUtils.build_type_registry([derived], headers.append)

        self.assertEqual([header.path for header in headers], ["shared/Base.h", "example/Derived.h"])
        self.assertEqual([(member.name, member.value) for member in headers[-1].declaration.values], [("Idle", 7)])
        self.assertEqual(headers[-1].includes, ("<cstdint>",))
        self.assertEqual(registry.named_types["shared.Base"].cpp_type_name, "::shared::Base")
        self.assertEqual(registry.named_types["example.Derived"].cpp_type_name, "::example::Derived")
        self.assertEqual(derived.values, ())

    def test_enum_inheritance_cycles_fail_before_any_header_notification(self):
        """Self-reference and multilevel cycles use the shared UUID dependency check."""
        for cycle in ("self", "indirect"):
            with self.subTest(cycle=cycle):
                first = EnumDataType(
                    name="First", source_kind=DataTypeSource.FRANCA, values=[EnumValue(name="FirstValue", value=1)]
                )
                if cycle == "self":
                    first = first.model_copy(update={"extends": first})
                    expected_chain = "First -> First"
                else:
                    second = EnumDataType(
                        name="Second",
                        source_kind=DataTypeSource.FRANCA,
                        extends=first,
                        values=[EnumValue(name="SecondValue", value=2)],
                    )
                    first.extends = second
                    expected_chain = "First -> Second -> First"
                headers = []

                with self.assertRaisesRegex(ValueError, "Cyclic datatype dependency detected: " + expected_chain):
                    DatatypeUtils.build_type_registry([first], headers.append)

                self.assertEqual(headers, [])

    def test_enum_unresolved_parent_is_rejected_before_notification(self):
        """Inheritance references must be resolved by the importer, not the generator."""
        derived = EnumDataType(
            name="Derived",
            source_kind=DataTypeSource.FRANCA,
            extends=Identifier("Missing"),
            values=[EnumValue(name="Active", value=1)],
        )
        headers = []

        with self.assertRaisesRegex(ValueError, "Unresolved datatype reference: Missing"):
            DatatypeUtils.build_type_registry([derived], headers.append)

        self.assertEqual(headers, [])

    def test_inherited_enum_values_must_fit_the_derived_storage(self):
        """A valid parent value cannot widen or change the signedness of the derived enum."""
        for parent_size, parent_signed, value in ((16, False, 256), (8, True, -1)):
            with self.subTest(size=parent_size, signed=parent_signed, value=value):
                base = EnumDataType(
                    name="Base",
                    source_kind=DataTypeSource.FRANCA,
                    size=parent_size,
                    signed=parent_signed,
                    values=[EnumValue(name="ParentValue", value=value)],
                )
                derived = EnumDataType(
                    name="Derived",
                    source_kind=DataTypeSource.FRANCA,
                    extends=base,
                    size=8,
                    values=[EnumValue(name="LocalValue", value=1)],
                )
                headers = []

                with self.assertRaisesRegex(ValueError, f"Derived.ParentValue = {value}"):
                    DatatypeUtils.build_type_registry([derived], headers.append)

                self.assertEqual([header.path for header in headers], ["Base.h"])

    def test_enum_inherited_name_and_disallowed_value_collisions_are_rejected(self):
        """Flattening never silently overrides names or bypasses the derived alias policy."""
        for local_name, local_value, message in (
            ("ParentValue", 1, "Duplicate enum literal name"),
            ("LocalValue", 0, "Enum value aliases are not allowed"),
        ):
            with self.subTest(name=local_name, value=local_value):
                base = EnumDataType(
                    name="Base", source_kind=DataTypeSource.FRANCA, values=[EnumValue(name="ParentValue", value=0)]
                )
                derived = EnumDataType(
                    name="Derived",
                    source_kind=DataTypeSource.FRANCA,
                    extends=base,
                    allow_value_aliases=False,
                    values=[EnumValue(name=local_name, value=local_value)],
                )
                headers = []

                with self.assertRaisesRegex(ValueError, message):
                    DatatypeUtils.build_type_registry([derived], headers.append)

                self.assertEqual([header.path for header in headers], ["Base.h"])

    def test_enum_inherited_numeric_aliases_are_preserved_by_default(self):
        """Equal values keep both declared names under the default derived enum policy."""
        base = EnumDataType(
            name="Base", source_kind=DataTypeSource.FRANCA, values=[EnumValue(name="ParentValue", value=0)]
        )
        derived = EnumDataType(
            name="Derived",
            source_kind=DataTypeSource.FRANCA,
            extends=base,
            values=[EnumValue(name="LocalValue", value=0)],
        )
        headers = []

        DatatypeUtils.build_type_registry([derived], headers.append)

        self.assertEqual(
            [(member.name, member.value) for member in headers[-1].declaration.values],
            [("LocalValue", 0), ("ParentValue", 0)],
        )


if __name__ == "__main__":
    unittest.main()
