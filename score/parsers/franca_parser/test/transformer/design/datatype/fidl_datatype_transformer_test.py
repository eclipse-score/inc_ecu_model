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

"""Integration tests for FIDL datatype declaration transformation."""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from lark.exceptions import VisitError

from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.common import DataTypeBase, DataTypeSource
from score.ecu_model.data_types.enum import EnumDataType
from score.ecu_model.data_types.map import MapDataType
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.model import ModelRegistry
from score.parsers.franca_parser.parser import FrancaParser
from score.parsers.franca_parser.transformer.fdepl_transformer import FDEPLTransformer
from score.parsers.franca_parser.transformer.fidl_transformer import FIDLTransformer
from score.parsers.franca_parser.transformer.file_graph_transformer import FrancaFileGraphTransformer

TEST_DATA_DIRECTORY = Path(__file__).parent / "test_data" / "datatype_definitions"
REFERENCE_DATA_DIRECTORY = Path(__file__).parent / "test_data" / "reference_resolution"


class FIDLDatatypeTransformerTest(unittest.TestCase):
    """Verify FIDL datatype declarations transform into Orion models."""

    def test_integer_callbacks_share_literal_conversion_and_errors(self) -> None:
        callbacks = {
            "lower": lambda value: FIDLTransformer.lower_dim(value)[1],
            "upper": lambda value: FIDLTransformer.upper_dim(value)[1],
            "fidl_integer": FIDLTransformer.integer,
            "fdepl_integer": FDEPLTransformer.integer,
        }
        for name, callback in callbacks.items():
            for literal, expected in (
                ("0", 0),
                ("00", 0),
                ("16", 16),
                ("0x10", 16),
                ("0X10", 16),
                ("0b10000", 16),
                ("0B10000", 16),
            ):
                with self.subTest(callback=name, literal=literal):
                    self.assertEqual(callback(literal), expected)
            for literal in ("08", "010", "invalid"):
                with self.subTest(callback=name, literal=literal), self.assertRaises(ValueError):
                    callback(literal)

    def test_array_bounds_and_enum_values_share_integer_syntax(self) -> None:
        for lower, upper in (("2", "16"), ("0x2", "0x10"), ("0b10", "0b10000")):
            with self.subTest(lower=lower, upper=upper), TemporaryDirectory() as directory:
                source_file = Path(directory) / "integers.fidl"
                source_file.write_text(
                    "package example typeCollection Types { "
                    f"array Samples of UInt8[{lower},{upper}] "
                    f"enumeration Limits {{ Lower = {lower} Upper = {upper} }} }}",
                    encoding="utf-8",
                )
                graph = FrancaFileGraphTransformer(FrancaParser([source_file], []).parse_files())
                graph.transform_files()
                array, enum = graph.transformed_files[source_file.resolve()].type_collections[0].datatypes
                self.assertEqual((array.dimension_min, array.dimension_max), (2, 16))
                self.assertEqual([value.value for value in enum.values], [2, 16])

    def test_array_bounds_and_enum_values_reject_nonzero_decimal_leading_zeros(self) -> None:
        for literal in ("08", "010"):
            for declaration in (
                f"array Samples of UInt8[{literal},16]",
                f"array Samples of UInt8[0,{literal}]",
                f"enumeration Limits {{ Value = {literal} }}",
            ):
                with self.subTest(declaration=declaration), TemporaryDirectory() as directory:
                    source_file = Path(directory) / "invalid.fidl"
                    source_file.write_text(
                        f"package example typeCollection Types {{ {declaration} }}", encoding="utf-8"
                    )
                    graph = FrancaFileGraphTransformer(FrancaParser([source_file], []).parse_files())
                    with self.assertRaisesRegex(VisitError, "invalid literal for int"):
                        graph.transform_files()

    def test_transform_files_given_valid_tc_versions_expect_datatype_declarations(self) -> None:
        for collection_name in ("Types", ""):
            for major, minor in ((1, 0), (0, 1)):
                with (
                    self.subTest(collection_name=collection_name, major=major, minor=minor),
                    TemporaryDirectory() as directory,
                ):
                    source_file = Path(directory) / "types.fidl"
                    source_file.write_text(
                        f"package example typeCollection {collection_name} {{ "
                        f"version {{ major {major} minor {minor} }} struct Payload {{}} }}",
                        encoding="utf-8",
                    )
                    parser = FrancaParser(root_files=[source_file], dependency_files=[])
                    graph = FrancaFileGraphTransformer(parser.parse_files())
                    graph.transform_files()
                    file_model = graph.transformed_files[source_file.resolve()]
                    self.assertEqual(file_model.type_collections[0].datatypes[0].name.as_str, "Payload")

    def test_transform_files_given_zero_tc_version_expect_validation_error(self) -> None:
        for collection_name in ("Types", ""):
            with self.subTest(collection_name=collection_name), TemporaryDirectory() as directory:
                source_file = Path(directory) / "types.fidl"
                source_file.write_text(
                    f"package example typeCollection {collection_name} {{ "
                    "version { major 0 minor 0 } struct Payload {} }",
                    encoding="utf-8",
                )
                parser = FrancaParser(root_files=[source_file], dependency_files=[])
                with self.assertRaisesRegex(VisitError, "greater than zero"):
                    FrancaFileGraphTransformer(parser.parse_files()).transform_files()

    def transform_to_registry(
        self,
        parser: FrancaParser,
        source_files: tuple[Path, ...],
    ) -> dict[str, list[DataTypeBase]]:
        existing_ids = set(ModelRegistry.elements)
        FrancaFileGraphTransformer(parser.parse_files()).transform_files()
        new_ids = set(ModelRegistry.elements) - existing_ids
        registry_bytes = ModelRegistry.serialize()
        ModelRegistry.deserialize(registry_bytes)
        datatypes = [
            element
            for element in ModelRegistry.elements.values()
            if element.id in new_ids and isinstance(element, DataTypeBase) and element.name is not None
        ]
        return {
            str(source_file.resolve()): [
                datatype for datatype in datatypes if datatype.source_uri == str(source_file.resolve())
            ]
            for source_file in source_files
        }

    def test_transform_files_given_datatype_declarations_expect_models_and_metadata(self) -> None:
        # Given a FIDL type collection containing each supported datatype declaration.
        source_file = TEST_DATA_DIRECTORY / "datatype_definitions.fidl"
        parser = FrancaParser(root_files=[source_file], dependency_files=[])

        # When the parser transforms the source through the FIDL file graph.
        datatypes = self.transform_to_registry(parser, (source_file,))[str(source_file.resolve())]

        # Then declarations retain their source ordering, metadata, and datatype semantics.
        self.assertEqual(
            [datatype.name.as_str for datatype in datatypes],
            [
                "Speed",
                "Mode",
                "Payload",
                "Value",
                "UnboundedArray",
                "MaximumBoundedArray",
                "OpenLowerBoundedArray",
                "BoundedArray",
                "Lookup",
            ],
        )
        self.assertTrue(all(datatype.namespace.as_str == "example.datatypes.Definitions" for datatype in datatypes))
        self.assertTrue(all(datatype.source_kind is DataTypeSource.FRANCA for datatype in datatypes))

        typedef = datatypes[0]
        enum = datatypes[1]
        struct = datatypes[2]
        unbounded_array = datatypes[4]
        open_lower_bounded_array = datatypes[6]
        bounded_array = datatypes[7]
        datatype_map = datatypes[8]

        self.assertIsInstance(typedef, TypedefDataType)
        self.assertIs(typedef.data_type, PrimitiveDataType.UINT32)
        self.assertIsInstance(enum, EnumDataType)
        self.assertEqual(
            [value.value for value in enum.values],
            [0, 5, 6, 16, 17, -2],
        )
        self.assertIsInstance(struct, StructDataType)
        self.assertIsInstance(struct.fields[1].data_type, ArrayDataType)
        self.assertTrue(struct.fields[1].data_type.is_inline)
        self.assertEqual(struct.fields[1].data_type.dimension_min, None)
        self.assertEqual(struct.fields[1].data_type.dimension_max, 8)
        self.assertIsInstance(unbounded_array, ArrayDataType)
        self.assertEqual((unbounded_array.dimension_min, unbounded_array.dimension_max), (None, None))
        self.assertEqual(
            (open_lower_bounded_array.dimension_min, open_lower_bounded_array.dimension_max),
            (None, 64),
        )
        self.assertEqual((bounded_array.dimension_min, bounded_array.dimension_max), (1, 64))
        self.assertIsInstance(datatype_map, MapDataType)
        self.assertIsInstance(datatype_map.key_type, PrimitiveDataType)
        self.assertIs(datatype_map.value_type, struct)

    def test_transform_files_given_file_imports_expect_imported_and_local_references_resolved(self) -> None:
        # Given a FIDL file importing named and anonymous type collections.
        root_file = REFERENCE_DATA_DIRECTORY / "file_only_root.fidl"
        shared_file = REFERENCE_DATA_DIRECTORY / "shared_types.fidl"
        anonymous_file = REFERENCE_DATA_DIRECTORY / "anonymous_types.fidl"
        parser = FrancaParser(
            root_files=[root_file],
            dependency_files=[shared_file, anonymous_file],
        )

        # When imports are transformed before the root file.
        datatypes_by_source = self.transform_to_registry(parser, (root_file, shared_file, anonymous_file))

        # Then references bind to their declared imported or local datatype models.
        root_datatypes = {datatype.name.as_str: datatype for datatype in datatypes_by_source[str(root_file.resolve())]}
        payload_alias = root_datatypes["PayloadAlias"]
        local_container = root_datatypes["LocalContainer"]
        local_item = root_datatypes["LocalItem"]
        shared_payload = datatypes_by_source[str(shared_file.resolve())][0]
        anonymous_payload = datatypes_by_source[str(anonymous_file.resolve())][0]

        self.assertIs(payload_alias.data_type, shared_payload)
        self.assertIs(local_container.fields[0].data_type, local_item)
        self.assertIs(local_container.fields[1].data_type, shared_payload)
        self.assertIs(local_container.fields[2].data_type, shared_payload)
        self.assertIs(local_container.fields[3].data_type, anonymous_payload)
        self.assertIs(local_container.fields[4].data_type, anonymous_payload)

    def test_transform_files_given_local_type_collections_expect_same_and_sibling_references_resolved(self) -> None:
        # Given one FIDL file with references to declarations in two type collections.
        source_file = REFERENCE_DATA_DIRECTORY / "local_type_collections.fidl"
        parser = FrancaParser(root_files=[source_file], dependency_files=[])

        # When the FIDL model root resolves references still pending after import lookup.
        datatypes = self.transform_to_registry(parser, (source_file,))[str(source_file.resolve())]

        # Then declarations in the same and sibling collections resolve within the file.
        datatypes_by_name = {datatype.name.as_str: datatype for datatype in datatypes}
        primary_payload = datatypes_by_name["PrimaryPayload"]
        local_references = datatypes_by_name["LocalReferences"]
        secondary_payload = datatypes_by_name["SecondaryPayload"]
        self.assertIs(local_references.fields[0].data_type, primary_payload)
        self.assertIs(local_references.fields[1].data_type, secondary_payload)

    def test_transform_files_given_duplicate_named_type_collections_expect_error(self) -> None:
        # Given a FIDL file with duplicate named type collections.
        source_file = REFERENCE_DATA_DIRECTORY / "duplicate_type_collections.fidl"
        parser = FrancaParser(root_files=[source_file], dependency_files=[])

        # When the FIDL model root validates top-level declaration names.
        with self.assertRaisesRegex(VisitError, "Duplicate ID SharedTypes"):
            FrancaFileGraphTransformer(parser.parse_files()).transform_files()

    def test_transform_files_given_circular_imports_expect_pending_references_resolved(self) -> None:
        # Given two FIDL files whose struct fields reference one another through imports.
        left_file = REFERENCE_DATA_DIRECTORY / "circular_left.fidl"
        right_file = REFERENCE_DATA_DIRECTORY / "circular_right.fidl"
        parser = FrancaParser(root_files=[left_file], dependency_files=[right_file])

        # When import traversal completes both declarations before final pending resolution.
        datatypes_by_source = self.transform_to_registry(parser, (left_file, right_file))

        # Then the reference deferred while the cycle was open is bound to the left declaration.
        left_payload = datatypes_by_source[str(left_file.resolve())][0]
        right_payload = datatypes_by_source[str(right_file.resolve())][0]
        self.assertIs(left_payload.fields[0].data_type, right_payload)
        self.assertIs(right_payload.fields[0].data_type, left_payload)

    def test_parse_files_given_imported_types_expect_model_registry_with_resolved_references(self) -> None:
        # Given a Bazel parser action over a root file and its imported datatype files.
        runfiles_root = Path(os.environ["RUNFILES_DIR"])
        output_path = next(runfiles_root.rglob("franca_datatype_model_registry.pkl"))

        # When the generated model registry is restored.
        ModelRegistry.deserialize(output_path.read_bytes())
        datatypes = {
            element.name.as_str: element
            for element in ModelRegistry.elements.values()
            if isinstance(element, DataTypeBase) and element.name is not None
        }

        # Then imported and local datatype references point at the registered model instances.
        shared_payload = datatypes["SharedPayload"]
        alias = datatypes["PayloadAlias"]
        local_container = datatypes["LocalContainer"]
        self.assertIsInstance(alias, TypedefDataType)
        self.assertIsInstance(local_container, StructDataType)
        self.assertIs(alias.data_type, shared_payload)
        self.assertIs(local_container.fields[0].data_type, datatypes["LocalItem"])
        self.assertIs(local_container.fields[1].data_type, shared_payload)
        self.assertIs(local_container.fields[2].data_type, shared_payload)
        self.assertIs(local_container.fields[3].data_type, datatypes["AnonymousPayload"])
        self.assertIs(local_container.fields[4].data_type, datatypes["AnonymousPayload"])


if __name__ == "__main__":
    unittest.main()
