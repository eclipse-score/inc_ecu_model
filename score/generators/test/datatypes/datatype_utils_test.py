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

"""Verify primitive mappings, typedef and enum generation, and generation failures."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.common import DataTypeSource
from score.ecu_model.data_types.composite import DataTypeField
from score.ecu_model.data_types.enum import EnumDataType, EnumValue
from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.data_types.union import UnionDataType
from score.ecu_model.model import ModelElement, ModelRegistry
from score.generators.src.datatypes.cpp_model import CppAlias, CppEnum, CppEnumerator, CppField, CppStruct
from score.generators.src.datatypes.datatype_collector import DatatypeCollector
from score.generators.src.datatypes.datatype_generator import DatatypeGenerator
from score.generators.src.datatypes.datatype_utils import DatatypeUtils


class DatatypeUtilsTest(unittest.TestCase):
    """Exercise primitive, typedef, enum, and basic struct support without demo inputs."""

    def setUp(self):
        """Isolate model objects registered during each test."""
        ModelRegistry.elements.clear()
        self.addCleanup(ModelRegistry.elements.clear)

    def test_all_supported_primitives_register_without_emitting_headers(self):
        """Primitives have explicit C++ spellings and includes, not standalone headers."""
        scenarios = (
            (PrimitiveDataType.BOOL, "bool", ()),
            (PrimitiveDataType.FLOAT, "float", ()),
            (PrimitiveDataType.DOUBLE, "double", ()),
            (PrimitiveDataType.STRING, "std::string", ("<string>",)),
            (PrimitiveDataType.INT8, "std::int8_t", ("<cstdint>",)),
            (PrimitiveDataType.INT16, "std::int16_t", ("<cstdint>",)),
            (PrimitiveDataType.INT32, "std::int32_t", ("<cstdint>",)),
            (PrimitiveDataType.INT64, "std::int64_t", ("<cstdint>",)),
            (PrimitiveDataType.UINT8, "std::uint8_t", ("<cstdint>",)),
            (PrimitiveDataType.UINT16, "std::uint16_t", ("<cstdint>",)),
            (PrimitiveDataType.UINT32, "std::uint32_t", ("<cstdint>",)),
            (PrimitiveDataType.UINT64, "std::uint64_t", ("<cstdint>",)),
        )
        for primitive, spelling, includes in scenarios:
            with self.subTest(primitive=primitive):
                headers = []
                registry = DatatypeUtils.build_type_registry([primitive, primitive], headers.append)
                self.assertEqual(headers, [])
                self.assertEqual(registry.named_types, {})
                self.assertEqual(len(registry.primitive_types), 1)
                self.assertEqual(registry.primitive_types[primitive].cpp_type_name, spelling)
                self.assertEqual(registry.primitive_types[primitive].required_includes, includes)

    def test_typedef_chain_emits_dependencies_once_before_the_owner(self):
        """Repeated roots and identity-preserving copies reuse dependency headers."""
        target = TypedefDataType(
            name="Text",
            namespace="example",
            source_kind=DataTypeSource.FRANCA,
            data_type=PrimitiveDataType.STRING,
        )
        alias = TypedefDataType(
            name="PublicText",
            namespace="example",
            source_kind=DataTypeSource.FRANCA,
            data_type=target,
        )
        original_model = alias.model_dump()
        copied_alias = alias.model_copy(deep=True)
        self.assertIsNot(copied_alias, alias)
        self.assertEqual(copied_alias.id, alias.id)
        headers = []
        registry = DatatypeUtils.build_type_registry([alias, target, alias, copied_alias], headers.append)
        self.assertEqual([header.path for header in headers], ["example/Text.h", "example/PublicText.h"])
        self.assertEqual(headers[0].declaration, CppAlias("Text", "std::string"))
        self.assertEqual(headers[0].includes, ("<string>",))
        self.assertEqual(headers[1].declaration, CppAlias("PublicText", "::example::Text"))
        self.assertEqual(headers[1].includes, ("example/Text.h",))
        self.assertEqual(registry.named_types["example.PublicText"].required_includes, ("example/PublicText.h",))
        self.assertEqual(alias.model_dump(), original_model)

    def test_typedef_guards_preserve_distinct_paths(self):
        """Distinct path spellings produce readable guards with path-specific digests."""
        datatypes = [
            TypedefDataType(
                name=name,
                namespace=namespace,
                source_kind=DataTypeSource.FRANCA,
                data_type=PrimitiveDataType.UINT8,
            )
            for namespace, name in (
                ("left_right", "Value"),
                ("left", "right_Value"),
                ("foo.bar", "Count"),
                ("foo_bar", "Count"),
                ("Mixed", "Count"),
                ("mixed", "Count"),
            )
        ]
        headers = []

        DatatypeUtils.build_type_registry(datatypes, headers.append)

        self.assertEqual(len(headers), len(datatypes))
        self.assertEqual(len({header.guard for header in headers}), len(headers))
        for header in headers:
            self.assertRegex(header.guard, r"^[A-Z][A-Z0-9_]*_[0-9A-F]{24}_$")
            readable = header.path.replace("/", "_").replace(".", "_").upper()
            digest = hashlib.sha256(header.path.encode("utf-8")).hexdigest()[:24].upper()
            self.assertEqual(header.guard, f"{readable}_{digest}_")
        repeated_headers = []
        DatatypeUtils.build_type_registry(datatypes, repeated_headers.append)
        self.assertEqual(repeated_headers, headers)

    def test_collector_preserves_order_without_filtering_entries(self):
        """Invalid entries and supported datatypes are passed to lowering unchanged."""
        element = ModelElement()
        alias = TypedefDataType(name="Count", source_kind=DataTypeSource.FRANCA, data_type=PrimitiveDataType.UINT8)
        record = StructDataType(name="Record", source_kind=DataTypeSource.FRANCA, fields=[])
        selected = DatatypeCollector.collect({"data_types": {element.id: element, alias.id: alias, record.id: record}})
        self.assertEqual(selected, (element, alias, record))

    def test_typedef_struct_target_emits_its_dependency_first(self):
        """Aliases reuse a completed struct's name and usage include."""
        record = StructDataType(name="Record", source_kind=DataTypeSource.FRANCA, fields=[])
        alias = TypedefDataType(name="Alias", source_kind=DataTypeSource.FRANCA, data_type=record)
        headers = []

        DatatypeUtils.build_type_registry([alias], headers.append)

        self.assertEqual([header.path for header in headers], ["Record.h", "Alias.h"])
        self.assertEqual(headers[-1].declaration, CppAlias("Alias", "::Record"))
        self.assertEqual(headers[-1].includes, ("Record.h",))

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

    def test_unresolved_typedef_target_fails_before_emission(self):
        """Identifier references must be resolved before generation."""
        for target in (Identifier("Missing"), QualifiedName((Identifier("example"), Identifier("Missing")))):
            with self.subTest(target=target):
                alias = TypedefDataType(name="Alias", source_kind=DataTypeSource.FRANCA, data_type=target)
                with self.assertRaisesRegex(ValueError, "Unresolved datatype reference"):
                    DatatypeUtils.build_type_registry([alias], lambda header: self.fail("Unexpected header"))

    def test_typedef_self_reference_reports_cycle_before_emission(self):
        """Direct self-reference is rejected by the same traversal as longer cycles."""
        alias = TypedefDataType(name="Alias", source_kind=DataTypeSource.FRANCA, data_type=PrimitiveDataType.UINT8)
        alias.data_type = alias
        with self.assertRaisesRegex(ValueError, "Alias -> Alias"):
            DatatypeUtils.build_type_registry([alias], lambda header: self.fail("Unexpected header"))

    def test_typedef_cycle_reports_the_active_dependency_chain(self):
        """A cyclic alias chain never emits a header."""
        first = TypedefDataType(name="First", source_kind=DataTypeSource.FRANCA, data_type=PrimitiveDataType.UINT8)
        second = TypedefDataType(name="Second", source_kind=DataTypeSource.FRANCA, data_type=first)
        first.data_type = second
        headers = []
        with self.assertRaisesRegex(ValueError, "First -> Second -> First"):
            DatatypeUtils.build_type_registry([first], headers.append)
        self.assertEqual(headers, [])

    def test_case_insensitive_names_conflict_within_the_same_namespace(self):
        """Distinct definitions cannot produce case-conflicting C++ names."""
        first = TypedefDataType(name="Count", source_kind=DataTypeSource.FRANCA, data_type=PrimitiveDataType.UINT8)
        second = TypedefDataType(name="count", source_kind=DataTypeSource.FRANCA, data_type=PrimitiveDataType.UINT8)
        with self.assertRaisesRegex(ValueError, "Case-insensitive type name conflict"):
            DatatypeUtils.build_type_registry([first, second], lambda header: None)

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

    def test_generator_accepts_empty_datatype_section(self):
        """An empty datatype section produces no headers."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "out"
            DatatypeGenerator().generate({"data_types": {}}, output_dir)
            self.assertFalse(output_dir.exists())

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

    def test_generator_rejects_non_datatype_entries_before_writing(self):
        """Non-datatype entries reach lowering and fail instead of being skipped."""
        element = ModelElement()
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "out"
            with self.assertRaisesRegex(TypeError, "Expected a datatype, got ModelElement"):
                DatatypeGenerator().generate({"data_types": {element.id: element}}, output_dir)
            self.assertFalse(output_dir.exists())

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

    def test_generator_missing_datatype_section_fails_before_writing(self):
        """Direct section access raises KeyError without producing headers."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "out"
            with self.assertRaisesRegex(KeyError, "data_types"):
                DatatypeGenerator().generate({}, output_dir)
            self.assertFalse(output_dir.exists())

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

    def test_array_and_union_dependencies_remain_unsupported(self):
        """Basic structs and aliases never silently omit unsupported dependencies."""
        targets = (
            ArrayDataType(name="Items", source_kind=DataTypeSource.FRANCA, data_type=PrimitiveDataType.UINT8),
            UnionDataType(name="Choice", source_kind=DataTypeSource.FRANCA, fields=[]),
        )
        for target in targets:
            record = StructDataType(
                name="Record",
                source_kind=DataTypeSource.FRANCA,
                fields=[DataTypeField(name="value", data_type=target)],
            )
            alias = TypedefDataType(name="Alias", source_kind=DataTypeSource.FRANCA, data_type=target)
            for datatype in (target, record, alias):
                with self.subTest(target=target.name, root=datatype.name):
                    headers = []

                    with self.assertRaisesRegex(NotImplementedError, "Unsupported datatype"):
                        DatatypeUtils.build_type_registry([datatype], headers.append)

                    self.assertEqual(headers, [])

    def test_struct_missing_name_is_rejected(self):
        """Struct declarations require a name for their generated header."""
        base = StructDataType(name="Base", source_kind=DataTypeSource.FRANCA)
        unnamed = base.model_copy(update={"name": None})
        with self.assertRaisesRegex(ValueError, "Structs require a declared name"):
            DatatypeUtils.build_type_registry([unnamed], lambda header: self.fail("Unexpected header"))

    def test_struct_dependency_callback_failure_stops_before_parent_and_later_roots(self):
        """A child must finish output before its parent can notify the caller."""
        child = StructDataType(name="Child", source_kind=DataTypeSource.FRANCA)
        parent = StructDataType(
            name="Parent",
            source_kind=DataTypeSource.FRANCA,
            fields=[DataTypeField(name="child", data_type=child)],
        )
        later = StructDataType(name="Later", source_kind=DataTypeSource.FRANCA)
        headers = []
        failure = RuntimeError("dependency rendering failed")

        def fail_on_dependency(header):
            headers.append(header)
            raise failure

        with self.assertRaises(RuntimeError) as raised:
            DatatypeUtils.build_type_registry([parent, later], fail_on_dependency)

        self.assertIs(raised.exception, failure)
        self.assertEqual([header.path for header in headers], ["Child.h"])


if __name__ == "__main__":
    unittest.main()
