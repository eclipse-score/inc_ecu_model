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

"""Integration tests for FDEPL type-collection deployment transformation."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.common import DataTypeKind, DataTypeSource
from score.ecu_model.data_types.enum import EnumDataType, EnumValue
from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.ecu_model.data_types.map import MapDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.data_types.union import UnionDataType
from score.parsers.franca_parser.deployment_property_applier import DeploymentPropertyApplier
from score.parsers.franca_parser.model.fdepl.fdepl_file import FDEPLFileModel
from score.parsers.franca_parser.model.fdepl.type_collection_deployment import (
    ArrayDeployment,
    EnumerationDeployment,
    EnumValueDeployment,
    MapDeployment,
    StructDeployment,
    TypeCollectionDeployment,
    TypedefDeployment,
    UnionDeployment,
)
from score.parsers.franca_parser.model.fidl.fidl_file import FIDLFileModel
from score.parsers.franca_parser.model.fidl.type_collection import TypeCollection
from score.parsers.franca_parser.parser import FrancaParser
from score.parsers.franca_parser.transformer.fdepl_transformer import FDEPLTransformer
from score.parsers.franca_parser.transformer.file_graph_transformer import (
    FrancaFileGraphTransformer,
)
from score.parsers.franca_parser.transformer.resolver.fdepl_resolver import FDEPLResolver

TEST_DATA_DIRECTORY = Path(__file__).parent / "test_data"


class FDEPLTypeCollectionTransformerTest(unittest.TestCase):
    """Verify type-collection deployments from a self-contained FDEPL graph."""

    def test_type_collection_deployment_requires_target(self) -> None:
        self.assertRaisesRegex(TypeError, "required keyword-only argument: 'target'", TypeCollectionDeployment)

    def test_fd_types_resolves_target_before_constructing_deployment(self) -> None:
        with TemporaryDirectory() as directory:
            design_path = Path(directory) / "types.fidl"
            deployment_path = Path(directory) / "types.fdepl"
            design_path.write_text("package demo\ntypeCollection Types {}\n", encoding="utf-8")
            deployment_path.write_text(
                'package deployment\nimport "types.fidl"\nspecification someip {}\n'
                "<** @description: ignored **>\n"
                "define someip for typeCollection demo.Types {}\n",
                encoding="utf-8",
            )
            parsed_file = FrancaParser([deployment_path], [design_path]).parse_files()[deployment_path.resolve()]
            target = TypeCollection(name=Identifier("Types"))
            design = FIDLFileModel(
                file_path=design_path.resolve(),
                namespace=QualifiedName((Identifier("demo"),)),
                type_collections=[target],
            )
            transformer = FDEPLTransformer({design.file_path: design}, parsed_file, DeploymentPropertyApplier())

            deployment = transformer.fd_types(QualifiedName((Identifier("demo"), Identifier("Types"))))

            self.assertIs(deployment.target, target)
            file_model = transformer.transform_file()
            self.assertEqual(file_model.file_path, parsed_file.file_path)
            self.assertIs(file_model.imported_files, parsed_file.imports)
            self.assertEqual(len(file_model.type_collection_deployments), 1)
            with self.assertRaisesRegex(
                ValueError, "Could not resolve FIDL type collection demo.Missing in .*types.fdepl"
            ):
                transformer.fd_types(QualifiedName((Identifier("demo"), Identifier("Missing"))))

    def test_resolve_deployment_rejects_mismatched_datatype_kind(self) -> None:
        owning_file = FDEPLFileModel(file_path=Path("invalid.fdepl"), namespace=None)
        target_name = Identifier("WrongTarget")
        cases = [
            (
                TypedefDeployment(deployed_type=target_name),
                EnumDataType(name=target_name, source_kind=DataTypeSource.FRANCA),
                DataTypeKind.TYPEDEF,
            ),
            (
                ArrayDeployment(deployed_type=target_name),
                EnumDataType(name=target_name, source_kind=DataTypeSource.FRANCA),
                DataTypeKind.ARRAY,
            ),
            (
                EnumerationDeployment(deployed_type=target_name),
                StructDataType(name=target_name, source_kind=DataTypeSource.FRANCA),
                DataTypeKind.ENUM,
            ),
            (
                StructDeployment(deployed_type=target_name),
                EnumDataType(name=target_name, source_kind=DataTypeSource.FRANCA),
                DataTypeKind.STRUCT,
            ),
            (
                UnionDeployment(deployed_type=target_name),
                EnumDataType(name=target_name, source_kind=DataTypeSource.FRANCA),
                DataTypeKind.UNION,
            ),
            (
                MapDeployment(deployed_type=target_name),
                EnumDataType(name=target_name, source_kind=DataTypeSource.FRANCA),
                DataTypeKind.MAP,
            ),
        ]

        for deployment, target, expected_kind in cases:
            with self.subTest(deployment=type(deployment).__name__):
                with self.assertRaises(ValueError) as raised:
                    FDEPLResolver._resolve_datatype(
                        deployment,
                        TypeCollection(name=None, datatypes=[target]),
                        owning_file,
                    )
                self.assertEqual(
                    str(raised.exception),
                    f"FIDL datatype {target_name.as_str} has kind {target.kind}, "
                    f"expected {expected_kind} in {owning_file.file_path}",
                )

    def test_transform_files_given_anonymous_type_collection_expect_target_bound_by_package(self) -> None:
        deployment_file = TEST_DATA_DIRECTORY / "anonymous_someip_deployment.fdepl"
        specification_file = TEST_DATA_DIRECTORY / "someip_deployment_spec.fdepl"
        types_file = TEST_DATA_DIRECTORY / "anonymous_types.fidl"
        parser = FrancaParser(
            root_files=[deployment_file],
            dependency_files=[specification_file, types_file],
        )

        transformer = FrancaFileGraphTransformer(parser.parse_files())
        transformer.transform_files()

        deployment = transformer.transformed_files[deployment_file.resolve()].type_collection_deployments[0]
        self.assertIsNone(deployment.target.name)
        self.assertEqual(deployment.target.datatypes[0].name.as_str, "Payload")

    def test_transform_files_given_someip_type_collection_deployment_expect_bound_datatype_deployments(self) -> None:
        deployment_file = TEST_DATA_DIRECTORY / "score_type_collection_someip_deployment.fdepl"
        specification_file = TEST_DATA_DIRECTORY / "someip_deployment_spec.fdepl"
        types_file = TEST_DATA_DIRECTORY / "score_type_collection_types.fidl"
        parser = FrancaParser(
            root_files=[deployment_file],
            dependency_files=[specification_file, types_file],
        )

        transformer = FrancaFileGraphTransformer(parser.parse_files())
        transformer.transform_files()

        deployment = transformer.transformed_files[deployment_file.resolve()].type_collection_deployments[0]
        self.assertEqual(deployment.specification.name.as_str, "someip")
        self.assertEqual(deployment.target.name.as_str, "TypeCollectionSkyLandmarks")
        self.assertEqual(deployment.name.as_str, "TypeCollectionSkyLandmarksSomeipStringDeployment_v1_0")
        self.assertEqual(
            [(parameter.name.as_str, parameter.value) for parameter in deployment.parameter_set],
            [("TypeCollectionMarker", 42)],
        )
        self.assertEqual(len(deployment.deployment_elements), 6)

        struct_deployment = deployment.deployment_elements[0]
        self.assertIsInstance(struct_deployment, StructDeployment)
        self.assertIsInstance(struct_deployment.deployed_type, StructDataType)
        self.assertEqual(struct_deployment.deployed_type.name.as_str, "OCRText")
        self.assertEqual(
            [(parameter.name.as_str, parameter.value) for parameter in struct_deployment.parameter_set],
            [("SomeIpStructLength", 42)],
        )
        self.assertEqual(struct_deployment.fields[0].deployed_type.name.as_str, "Character")
        self.assertEqual(struct_deployment.fields[0].parameter_set[0].name.as_str, "ScoreProperty481")
        self.assertEqual(struct_deployment.fields[0].parameter_set[0].value, 42)
        self.assertNotIn(
            "SomeIpStructLength",
            struct_deployment.deployed_type.deployment_properties,
        )

        union_deployment = deployment.deployment_elements[1]
        self.assertIsInstance(union_deployment, UnionDeployment)
        self.assertIsInstance(union_deployment.deployed_type, UnionDataType)
        self.assertEqual(union_deployment.deployed_type.name.as_str, "Payload")
        self.assertEqual(
            [(parameter.name.as_str, parameter.value) for parameter in union_deployment.parameter_set],
            [("SomeIpUnionLength", 42)],
        )
        self.assertEqual(union_deployment.fields[0].deployed_type.name.as_str, "text")
        self.assertEqual(union_deployment.fields[0].parameter_set[0].name.as_str, "ScoreProperty481")
        self.assertEqual(union_deployment.fields[0].parameter_set[0].value, 42)

        typedef_deployment = deployment.deployment_elements[2]
        self.assertIsInstance(typedef_deployment, TypedefDeployment)
        self.assertIsInstance(typedef_deployment.deployed_type, TypedefDataType)
        self.assertEqual(typedef_deployment.deployed_type.name.as_str, "DisplayText")
        self.assertEqual(typedef_deployment.parameter_set[0].name.as_str, "ScoreProperty481")
        self.assertEqual(typedef_deployment.parameter_set[0].value, 42)

        array_deployment = deployment.deployment_elements[3]
        self.assertIsInstance(array_deployment, ArrayDeployment)
        self.assertIsInstance(array_deployment.deployed_type, ArrayDataType)
        self.assertEqual(array_deployment.deployed_type.name.as_str, "byteArray")
        self.assertEqual(
            [(parameter.name.as_str, parameter.value) for parameter in array_deployment.parameter_set],
            [("ScoreProperty247", 42), ("ScoreProperty246", 42)],
        )

        enumeration_deployment = deployment.deployment_elements[4]
        self.assertIsInstance(enumeration_deployment, EnumerationDeployment)
        self.assertIsInstance(enumeration_deployment.deployed_type, EnumDataType)
        self.assertEqual(enumeration_deployment.deployed_type.name.as_str, "SeverityEnum")
        self.assertEqual(enumeration_deployment.parameter_set[0].name.as_str, "ScoreProperty069")
        self.assertEqual(enumeration_deployment.parameter_set[0].value.as_str, "ScoreValue238")
        enum_value_deployment = enumeration_deployment.enumerators[0]
        self.assertIsInstance(enum_value_deployment, EnumValueDeployment)
        self.assertIsInstance(enum_value_deployment.deployed_type, EnumValue)
        self.assertEqual(enum_value_deployment.deployed_type.name.as_str, "Info")
        self.assertEqual(enum_value_deployment.parameter_set[0].name.as_str, "ScoreProperty074")
        self.assertEqual(enum_value_deployment.parameter_set[0].value.as_str, "ScoreValue102")

        map_deployment = deployment.deployment_elements[5]
        self.assertIsInstance(map_deployment, MapDeployment)
        self.assertIsInstance(map_deployment.deployed_type, MapDataType)
        self.assertEqual(map_deployment.deployed_type.name.as_str, "MetaInfoType")
        self.assertIsInstance(map_deployment.deployed_type.key_type, TypedefDataType)
        self.assertEqual(map_deployment.deployed_type.key_type.name.as_str, "DisplayText")
        self.assertEqual(
            [(parameter.name.as_str, parameter.value.as_str) for parameter in map_deployment.key],
            [("MapKeyParam", "MapKeyValue")],
        )
        self.assertEqual(
            [(parameter.name.as_str, parameter.value.as_str) for parameter in map_deployment.value],
            [("MapValueParam", "MapValValue")],
        )


if __name__ == "__main__":
    unittest.main()
