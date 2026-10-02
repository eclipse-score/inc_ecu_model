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

"""Integration tests for legacy-compatible Franca datatype deployment properties."""

import unittest
from pathlib import Path

from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.common import DataTypeSource
from score.ecu_model.data_types.enum import EnumDataType
from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.data_types.union import UnionDataType
from score.parsers.franca_parser.deployment_property_applier import DeploymentPropertyApplier
from score.parsers.franca_parser.model.fdepl.definition import DeploymentParameter
from score.parsers.franca_parser.model.fdepl.specification import (
    DeploymentPropertyType,
    DeploymentPropertyTypeReference,
    DeploymentSpecification,
    ParameterDeclaration,
)
from score.parsers.franca_parser.model.fdepl.type_collection_deployment import (
    EnumerationDeployment,
    FieldDeployment,
    MapDeployment,
    StructDeployment,
    TypeCollectionDeployment,
    TypedefDeployment,
)
from score.parsers.franca_parser.parser import FrancaParser
from score.parsers.franca_parser.transformer.file_graph_transformer import (
    FrancaFileGraphTransformer,
)

TEST_DATA_DIRECTORY = Path(__file__).parents[5] / "test_data/franca/deployment"


class DeploymentPropertyApplierTest(unittest.TestCase):
    """Verify deployment properties applied from transformed FDEPL definitions."""

    def test_apply_skips_unsupported_and_enumeration_deployments(self) -> None:
        applier = DeploymentPropertyApplier()
        specification = self._specification_with_integer_property()
        target = self._typedef_target()

        applier._apply_deployment_element(MapDeployment(deployed_type=target), specification)
        self.assertEqual(target.deployment_properties, {})

        enumeration = EnumDataType(name=Identifier("Enumeration"), source_kind=DataTypeSource.FRANCA)
        specification.hosts["enumerations"] = specification.hosts.pop("typedefs")
        applier._apply_deployment_element(
            EnumerationDeployment(
                deployed_type=enumeration,
                parameter_set=[DeploymentParameter(name=Identifier("property"), value=1)],
            ),
            specification,
        )
        self.assertEqual(enumeration.deployment_properties, {"property": 1})

    def test_apply_warns_for_undeclared_property_and_rejects_unresolved_base_specification(self) -> None:
        applier = DeploymentPropertyApplier()
        specification = self._specification_with_integer_property()
        target = self._typedef_target()

        with self.assertLogs(level="WARNING") as logs:
            applier._apply_parameters(
                target,
                [
                    DeploymentParameter(name=Identifier("property"), value=1),
                    DeploymentParameter(name=Identifier("unknown"), value=42),
                ],
                specification,
                {"typedefs"},
            )
        self.assertIn("Ignoring undeclared deployment property unknown", logs.output[0])

        specification.base_specifications.append(QualifiedName((Identifier("base"),)))
        with self.assertRaisesRegex(ValueError, "Unresolved base deployment specification"):
            applier._declarations_for_hosts(specification, {"typedefs"})

    def test_apply_rejects_unresolved_deployment_specification_and_targets(self) -> None:
        applier = DeploymentPropertyApplier()
        specification = self._specification_with_integer_property()

        with self.assertRaisesRegex(ValueError, "Unresolved deployment specification"):
            applier.apply_type_collection_deployment(
                TypeCollectionDeployment(specification=QualifiedName((Identifier("specification"),)))
            )
        with self.assertRaisesRegex(ValueError, "Unresolved datatype deployment target"):
            applier._apply_deployment_element(TypedefDeployment(), specification)

        struct = StructDataType(name=Identifier("Struct"), source_kind=DataTypeSource.FRANCA)
        with self.assertRaisesRegex(ValueError, "Unresolved field deployment target"):
            applier._apply_deployment_element(
                StructDeployment(
                    deployed_type=struct,
                    parameter_set=[DeploymentParameter(name=Identifier("property"), value=1)],
                    fields=[FieldDeployment()],
                ),
                specification,
            )

    def test_apply_rejects_missing_required_property(self) -> None:
        with self.assertRaisesRegex(ValueError, "Required deployment property property is not set"):
            DeploymentPropertyApplier()._apply_parameters(
                self._typedef_target(),
                [],
                self._specification_with_integer_property(),
                {"typedefs"},
            )

    def test_apply_rejects_invalid_property_shape_and_scalar_value(self) -> None:
        applier = DeploymentPropertyApplier()
        specification = self._specification_with_integer_property()

        with self.assertRaisesRegex(ValueError, "Invalid shape for deployment property property"):
            applier._apply_parameters(
                self._typedef_target(),
                [DeploymentParameter(name=Identifier("property"), value=[1])],
                specification,
                {"typedefs"},
            )
        with self.assertRaisesRegex(ValueError, "Invalid value for deployment property property"):
            applier._apply_parameters(
                self._typedef_target(),
                [DeploymentParameter(name=Identifier("property"), value="one")],
                specification,
                {"typedefs"},
            )

    @staticmethod
    def _typedef_target() -> TypedefDataType:
        return TypedefDataType(
            name=Identifier("Target"),
            source_kind=DataTypeSource.FRANCA,
            data_type=PrimitiveDataType.UINT8,
        )

    @staticmethod
    def _specification_with_integer_property() -> DeploymentSpecification:
        declaration = ParameterDeclaration(
            host="typedefs",
            name=Identifier("property"),
            type_reference=DeploymentPropertyTypeReference(DeploymentPropertyType.INTEGER),
        )
        return DeploymentSpecification(
            name=QualifiedName((Identifier("specification"),)),
            hosts={"typedefs": {"property": declaration}},
        )

    def test_apply_given_someip_datatype_deployments_expect_legacy_compatible_properties(self) -> None:
        deployment_file = TEST_DATA_DIRECTORY / "datatype_properties_deployment.fdepl"
        types_file = TEST_DATA_DIRECTORY / "datatype_properties.fidl"
        specification_file = TEST_DATA_DIRECTORY / "score_network_SOMEIP_deployment_spec.fdepl"
        architecture_file = TEST_DATA_DIRECTORY / "score_architecture_deployment_spec.fdepl"
        parser = FrancaParser(
            root_files=[deployment_file],
            dependency_files=[types_file, specification_file, architecture_file],
        )
        transformed_files = FrancaFileGraphTransformer(parser.parse_files()).transform_files()

        type_collection = transformed_files[types_file.resolve()].type_collections[0]
        datatypes_by_name = {datatype.name.as_str: datatype for datatype in type_collection.datatypes}
        message_text = datatypes_by_name["MessageText"]
        message = datatypes_by_name["Message"]
        payload = datatypes_by_name["Payload"]
        message_list = datatypes_by_name["MessageList"]
        status = datatypes_by_name["Status"]
        self.assertIsInstance(message_text, TypedefDataType)
        self.assertIsInstance(message, StructDataType)
        self.assertIsInstance(payload, UnionDataType)
        self.assertIsInstance(message_list, ArrayDataType)
        self.assertIsInstance(status, EnumDataType)

        self.assertEqual(
            message_text.deployment_properties,
            {"ScoreProperty481": 42, "ScoreProperty482": 42},
        )
        self.assertEqual(
            message.deployment_properties,
            {"ScoreProperty483": 42, "ScoreProperty493": False},
        )
        self.assertEqual(
            message.fields[0].deployment_properties,
            {
                "ScoreProperty481": 42,
                "ScoreProperty347": 42,
                "ScoreProperty346": 42,
                "ScoreProperty345": 42,
                "ScoreProperty482": 42,
            },
        )
        self.assertEqual(payload.deployment_properties, {"ScoreProperty484": True})
        self.assertEqual(
            message_list.deployment_properties,
            {
                "ScoreProperty347": 42,
                "ScoreProperty346": 42,
                "ScoreProperty345": 42,
                "ScoreProperty481": 42,
                "ScoreProperty482": 42,
            },
        )
        self.assertEqual(status.deployment_properties, {"ScoreProperty405": 42})


if __name__ == "__main__":
    unittest.main()
