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

import os
from pathlib import Path
import unittest

from score.ecu_model.data_types.common import DataTypeBase
from score.ecu_model.data_types.enum import EnumDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.union import UnionDataType
from score.ecu_model.model import ModelRegistry
from score.ecu_model.query import datatypes_by_name


def load_combined_datatypes() -> dict[str, DataTypeBase]:
    ModelRegistry.deserialize(Path(os.environ["COMBINED_MODEL"]).read_bytes())
    return datatypes_by_name()


def field_types(struct: StructDataType) -> dict[str, object]:
    return {field.name.as_str: field.data_type for field in struct.fields}


class EcuModelParseFrancaInputsTest(unittest.TestCase):
    def test_rule_given_franca_root_with_dependency_expect_imported_type_resolved(self) -> None:
        datatypes = load_combined_datatypes()

        root_value = datatypes["example.franca.root.RootTypes.RootValue"]
        imported_value = datatypes["example.franca.imported.ImportedTypes.ImportedValue"]
        self.assertIs(field_types(root_value)["importedValue"], imported_value)

    def test_rule_given_two_franca_roots_sharing_a_dependency_expect_both_reference_one_shared_type(self) -> None:
        datatypes = load_combined_datatypes()

        shared_value = datatypes["example.franca.shared.SharedTypes.SharedValue"]
        first_value = datatypes["example.franca.first.FirstTypes.FirstValue"]
        second_value = datatypes["example.franca.second.SecondTypes.SecondValue"]
        self.assertIs(field_types(first_value)["sharedValue"], shared_value)
        self.assertIs(field_types(second_value)["sharedValue"], shared_value)

    def test_rule_given_franca_import_cycle_expect_types_reference_each_other(self) -> None:
        datatypes = load_combined_datatypes()

        left_value = datatypes["example.franca.cycle.LeftTypes.LeftValue"]
        right_value = datatypes["example.franca.cycle.RightTypes.RightValue"]
        self.assertIs(field_types(left_value)["rightValue"], right_value)
        self.assertIs(field_types(right_value)["leftValue"], left_value)

    def test_rule_given_fdepl_root_with_fidl_and_spec_dependencies_expect_deployment_properties_applied(self) -> None:
        datatypes = load_combined_datatypes()

        payload = datatypes["example.deployment.DeploymentTypes.Payload"]
        status = datatypes["example.deployment.DeploymentTypes.Status"]
        self.assertIsInstance(payload, UnionDataType)
        self.assertEqual(payload.deployment_properties, {"ScoreProperty484": True})
        self.assertIsInstance(status, EnumDataType)
        self.assertEqual(status.deployment_properties, {"ScoreProperty405": 42})


class EcuModelParseProtobufInputsTest(unittest.TestCase):
    def test_rule_given_proto_with_dependency_expect_cross_file_reference_resolved(self) -> None:
        datatypes = load_combined_datatypes()

        request = datatypes["integration.consumer.Request"]
        self.assertIs(field_types(request)["payload"], datatypes["integration.shared.Payload"])

    def test_rule_given_several_independent_protos_expect_all_parsed(self) -> None:
        datatypes = load_combined_datatypes()

        self.assertIsInstance(datatypes["integration.pipeline.NestedTypeConsumer"], StructDataType)
        self.assertIsInstance(datatypes["integration.pipeline.collections.Shape"], StructDataType)

    def test_rule_given_proto_custom_options_expect_deployment_properties(self) -> None:
        datatypes = load_combined_datatypes()

        request = datatypes["integration.deployment.ConfiguredRequest"]
        self.assertEqual(
            request.deployment_properties,
            {
                "integration.deployment.file_deployment.scope": "file",
                "integration.deployment.message_deployment.scope": "message",
            },
        )


if __name__ == "__main__":
    unittest.main()
