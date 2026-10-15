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

"""Validate real protobuf custom and standard option ingestion."""

from __future__ import annotations

import os
import pickle
import unittest
from pathlib import Path

from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.enum import EnumDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.union import UnionDataType


class ProtobufOptionsIntegrationTest(unittest.TestCase):
    """Test option ingestion through the public parser API."""

    def test_promotes_custom_option_descriptions_and_flattens_other_properties(self):
        registry = load_options_registry()

        deployment_namespace = ("integration", "deployment")
        request = _find_type_by_name(registry, "ConfiguredRequest", deployment_namespace)
        self.assertIsInstance(request, StructDataType)
        fields = {field.name.as_str: field for field in request.fields}
        self.assertEqual(request.description, "Request description")
        self.assertEqual(
            request.deployment_properties,
            {
                "integration.deployment.file_deployment.scope": "file",
                "integration.deployment.message_deployment.scope": "message",
            },
        )
        self.assertEqual(
            fields["payload"].deployment_properties,
            {
                "integration.deployment.field_deployment.transport": "in_memory",
                "integration.deployment.field_deployment.queue_depth": 16,
            },
        )
        self.assertEqual(fields["payload"].description, "Payload description\nPayload continuation")

        bounded_payloads = fields["bounded_payloads"]
        self.assertIsInstance(bounded_payloads.data_type, ArrayDataType)
        self.assertTrue(bounded_payloads.data_type.is_inline)
        self.assertEqual(bounded_payloads.data_type.dimension_min, 0)
        self.assertEqual(bounded_payloads.data_type.dimension_max, 32)
        self.assertEqual(bounded_payloads.deployment_properties, {})

        alternative = fields["alternative"].data_type
        self.assertIsInstance(alternative, UnionDataType)
        self.assertEqual(alternative.description, "Alternative description")
        self.assertEqual(
            alternative.deployment_properties,
            {
                "integration.deployment.file_deployment.scope": "file",
                "integration.deployment.oneof_deployment.scope": "oneof",
            },
        )

        file_description_default = _find_type_by_name(registry, "FileDescriptionDefault", deployment_namespace)
        self.assertIsInstance(file_description_default, StructDataType)
        self.assertEqual(file_description_default.description, "")
        self.assertEqual(
            file_description_default.deployment_properties,
            {"integration.deployment.file_deployment.scope": "file"},
        )

        state = _find_type_by_name(registry, "ConfiguredState", deployment_namespace)
        self.assertIsInstance(state, EnumDataType)
        self.assertEqual(state.description, "State description")
        self.assertEqual(
            state.deployment_properties,
            {
                "integration.deployment.file_deployment.scope": "file",
                "integration.deployment.enum_deployment.scope": "enum",
                "integration.deployment.enum_deployment.size": "ES_8",
            },
        )
        self.assertEqual(state.size, 8)
        self.assertFalse(state.signed)
        self.assertEqual(state.values[0].description, "Unspecified state")
        self.assertEqual(
            state.values[0].deployment_properties,
            {
                "integration.deployment.enum_value_deployment.scope": "enum_value",
            },
        )

        state_16 = _find_type_by_name(registry, "ConfiguredState16", deployment_namespace)
        self.assertIsInstance(state_16, EnumDataType)
        self.assertEqual(state_16.size, 16)
        self.assertFalse(state_16.signed)

        state_32 = _find_type_by_name(registry, "ConfiguredState32", deployment_namespace)
        self.assertIsInstance(state_32, EnumDataType)
        self.assertEqual(state_32.size, 32)
        self.assertFalse(state_32.signed)

    def test_preserves_explicit_standard_options(self):
        registry = load_options_registry()

        expected_file_properties = {
            "google.protobuf.FileOptions.java_package": "integration.standard_options.generated",
            "google.protobuf.FileOptions.optimize_for": "LITE_RUNTIME",
            "google.protobuf.FileOptions.deprecated": True,
        }
        standard_namespace = ("integration", "standard_options")
        message = _find_type_by_name(registry, "StandardOptionMessage", standard_namespace)
        self.assertIsInstance(message, StructDataType)
        self.assertEqual(
            message.deployment_properties,
            {
                **expected_file_properties,
                "google.protobuf.MessageOptions.deprecated": True,
            },
        )
        fields = {field.name.as_str: field for field in message.fields}
        self.assertEqual(
            fields["deprecated_value"].deployment_properties,
            {"google.protobuf.FieldOptions.deprecated": True},
        )
        self.assertEqual(
            fields["unpacked_values"].deployment_properties,
            {"google.protobuf.FieldOptions.packed": False},
        )

        state = _find_type_by_name(registry, "StandardOptionState", standard_namespace)
        self.assertIsInstance(state, EnumDataType)
        self.assertEqual(
            state.deployment_properties,
            {
                **expected_file_properties,
                "google.protobuf.EnumOptions.allow_alias": True,
                "google.protobuf.EnumOptions.deprecated": True,
            },
        )
        self.assertTrue(state.allow_value_aliases)
        self.assertEqual(
            state.values[0].deployment_properties,
            {"google.protobuf.EnumValueOptions.deprecated": True},
        )


def load_options_registry():
    """Load the UUID-keyed registry generated by the Bazel parser target."""
    runfiles_root = Path(os.environ["RUNFILES_DIR"])
    output_path = next(runfiles_root.rglob("options_model_registry.pkl"))
    return pickle.loads(output_path.read_bytes())


def _find_type_by_name(registry, name, expected_namespace):
    matches = [element for element in registry.values() if element.name is not None and element.name.as_str == name]
    if len(matches) != 1:
        raise AssertionError(f"Expected one data type named {name}, found {len(matches)}")
    element = matches[0]
    actual_namespace = tuple(part.as_str for part in element.namespace.names)
    if actual_namespace != expected_namespace:
        raise AssertionError(f"Expected namespace {expected_namespace} for {name}, found {actual_namespace}")
    return element


if __name__ == "__main__":
    unittest.main()
