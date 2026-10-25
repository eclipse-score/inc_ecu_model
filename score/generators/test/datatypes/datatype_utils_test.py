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

"""Verify primitive mappings, typedef dependencies, and generation failures."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from score.ecu_model.data_types.common import DataTypeSource
from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.model import ModelElement, ModelRegistry
from score.generators.src.datatypes.cpp_model import CppAlias
from score.generators.src.datatypes.datatype_collector import DatatypeCollector
from score.generators.src.datatypes.datatype_generator import DatatypeGenerator
from score.generators.src.datatypes.datatype_utils import DatatypeUtils


class DatatypeUtilsTest(unittest.TestCase):
    """Exercise the first supported datatype scope without demo inputs."""

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
        """Invalid entries and unsupported datatypes are passed to lowering unchanged."""
        element = ModelElement()
        alias = TypedefDataType(name="Count", source_kind=DataTypeSource.FRANCA, data_type=PrimitiveDataType.UINT8)
        unsupported = StructDataType(name="Record", source_kind=DataTypeSource.FRANCA, fields=[])
        selected = DatatypeCollector.collect(
            {"data_types": {element.id: element, alias.id: alias, unsupported.id: unsupported}}
        )
        self.assertEqual(selected, (element, alias, unsupported))
        with self.assertRaisesRegex(NotImplementedError, "Record"):
            DatatypeUtils.build_type_registry([unsupported], lambda header: self.fail("Unexpected header"))

    def test_unsupported_typedef_target_fails_before_emission(self):
        """Aliases cannot depend on declaration kinds outside the first scope."""
        unsupported = StructDataType(name="Record", source_kind=DataTypeSource.FRANCA, fields=[])
        alias = TypedefDataType(name="Alias", source_kind=DataTypeSource.FRANCA, data_type=unsupported)
        headers = []
        with self.assertRaisesRegex(NotImplementedError, "Unsupported datatype: Record"):
            DatatypeUtils.build_type_registry([alias], headers.append)
        self.assertEqual(headers, [])

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

    def test_generator_rejects_non_datatype_entries_before_writing(self):
        """Non-datatype entries reach lowering and fail instead of being skipped."""
        element = ModelElement()
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "out"
            with self.assertRaisesRegex(TypeError, "Expected a datatype, got ModelElement"):
                DatatypeGenerator().generate({"data_types": {element.id: element}}, output_dir)
            self.assertFalse(output_dir.exists())

    def test_generator_missing_datatype_section_fails_before_writing(self):
        """Direct section access raises KeyError without producing headers."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "out"
            with self.assertRaisesRegex(KeyError, "data_types"):
                DatatypeGenerator().generate({}, output_dir)
            self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
