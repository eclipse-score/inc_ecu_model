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

"""Validate end-to-end Protobuf ingestion through the public parser API."""

from __future__ import annotations

import os
import pickle
import unittest
from pathlib import Path

from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.enum import EnumDataType
from score.ecu_model.data_types.map import MapDataType
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.union import UnionDataType


class ProtobufPipelineIntegrationTest(unittest.TestCase):
    """Test successful end-to-end protobuf ingestion scenarios."""

    def test_resolves_nested_struct_and_enum_fields_from_another_message(self):
        registry = load_pipeline_registry()

        nested_struct = _find_type_by_name(
            registry, "NestedPayload", ("integration", "pipeline", "NestedTypeContainer")
        )
        nested_enum = _find_type_by_name(registry, "NestedState", ("integration", "pipeline", "NestedTypeContainer"))
        top_level_enum = _find_type_by_name(registry, "TopLevelState", ("integration", "pipeline"))

        nested_type_consumer = _find_type_by_name(registry, "NestedTypeConsumer", ("integration", "pipeline"))
        self.assertIsInstance(nested_struct, StructDataType)
        self.assertIsInstance(nested_enum, EnumDataType)
        self.assertIsInstance(top_level_enum, EnumDataType)
        self.assertIsInstance(nested_type_consumer, StructDataType)
        fields = {field.name.as_str: field for field in nested_type_consumer.fields}
        self.assertIs(fields["payload"].data_type, nested_struct)
        self.assertIs(fields["state"].data_type, nested_enum)
        self.assertIs(fields["top_level_state"].data_type, top_level_enum)

    def test_returns_resolved_collections_and_oneof_models(self):
        registry = load_pipeline_registry()
        package_namespace = ("integration", "pipeline", "collections")
        shape = _find_type_by_name(registry, "Shape", package_namespace)
        child = _find_type_by_name(registry, "Child", package_namespace)
        state = _find_type_by_name(registry, "State", package_namespace)
        external = _find_type_by_name(registry, "External", package_namespace)
        external_entry = _find_type_by_name(registry, "CountsEntry", (*package_namespace, "External"))

        self.assertIsInstance(shape, StructDataType)
        self.assertIsInstance(child, StructDataType)
        self.assertIsInstance(state, EnumDataType)
        self.assertIsInstance(external, StructDataType)
        self.assertIsInstance(external_entry, StructDataType)
        self.assertIs(external.nested_structs[0], external_entry)

        fields = {field.name.as_str: field for field in shape.fields}
        self.assertTrue(fields["nickname"].optional)
        self.assertIs(fields["nickname"].data_type, PrimitiveDataType.STRING)
        self.assertIsInstance(fields["counts"].data_type, MapDataType)
        self.assertIs(fields["counts"].data_type.key_type, PrimitiveDataType.STRING)
        self.assertIs(fields["counts"].data_type.value_type, child)

        identity = fields["identity"].data_type
        self.assertIsInstance(identity, UnionDataType)
        self.assertEqual([field.name.as_str for field in identity.fields], ["email", "child"])
        self.assertIs(identity.fields[1].data_type, child)
        self.assertIsInstance(fields["children"].data_type, ArrayDataType)
        self.assertIs(fields["children"].data_type.data_type, child)
        self.assertIs(fields["state"].data_type, state)
        self.assertIs(fields["external_entry"].data_type, external_entry)

    def test_resolves_cross_file_references_from_a_direct_import(self):
        registry = load_pipeline_registry()

        payload = _find_type_by_name(registry, "Payload", ("integration", "shared"))
        request = _find_type_by_name(registry, "Request", ("integration", "consumer"))
        self.assertIsInstance(payload, StructDataType)
        self.assertIsInstance(request, StructDataType)
        fields = {field.name.as_str: field for field in request.fields}
        self.assertIs(fields["payload"].data_type, payload)
        self.assertIsInstance(fields["payloads"].data_type, ArrayDataType)
        self.assertIs(fields["payloads"].data_type.data_type, payload)
        self.assertIsInstance(fields["payloads_by_id"].data_type, MapDataType)
        self.assertIs(fields["payloads_by_id"].data_type.value_type, payload)
        alternative_payload = fields["alternative_payload"].data_type
        self.assertIsInstance(alternative_payload, UnionDataType)
        self.assertIs(alternative_payload.fields[0].data_type, payload)


def load_pipeline_registry():
    """Load the UUID-keyed registry generated by the Bazel parser target."""
    runfiles_root = Path(os.environ["RUNFILES_DIR"])
    output_path = next(runfiles_root.rglob("pipeline_model_registry.pkl"))
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
