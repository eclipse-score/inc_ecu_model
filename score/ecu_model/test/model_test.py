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

import pickle
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from pydantic import ValidationError

from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.common import DataTypeSource
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.model import ModelElement, ModelRegistry
from score.ecu_model.query import datatypes_by_name


class TestModelRegistry(unittest.TestCase):
    def test_root_instantiation_succeeds(self) -> None:
        root = ModelRegistry()
        self.assertIsInstance(root, ModelRegistry)

    def test_root_instance_is_not_registered(self) -> None:
        root = ModelRegistry()
        self.assertNotIn(root, ModelRegistry.elements.values())


class TestModelElement(unittest.TestCase):
    def test_default_fields(self) -> None:
        element = ModelElement()
        self.assertIsInstance(element.id, UUID)
        self.assertEqual(element.description, "")

    def test_custom_description(self) -> None:
        element = ModelElement(description="Another test element")
        self.assertEqual(element.description, "Another test element")

    def test_registered_in_the_registry(self) -> None:
        element = ModelElement()
        self.assertIs(ModelRegistry.elements[element.id], element)

    def test_duplicate_id_raises_validation_error(self) -> None:
        shared_id = uuid4()
        ModelElement(id=shared_id)
        with self.assertRaises(ValidationError):
            ModelElement(id=shared_id)

    def test_str_representation(self) -> None:
        element = ModelElement(description="desc")
        self.assertEqual(str(element), f"ModelElement(id={element.id}, description=desc)")

    def test_assignment_is_validated(self) -> None:
        element = ModelElement()
        element.description = "updated"
        self.assertEqual(element.description, "updated")

    def test_invalid_assignment_raises_validation_error(self) -> None:
        element = ModelElement()
        with self.assertRaises(ValidationError):
            element.id = "not-a-uuid"


class TestSerialization(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_registry = dict(ModelRegistry.elements)
        ModelRegistry.elements.clear()

    def tearDown(self) -> None:
        ModelRegistry.elements.clear()
        ModelRegistry.elements.update(self._saved_registry)

    def test_round_trip_restores_all_elements(self) -> None:
        elements = [ModelElement(description="first"), ModelElement(description="second")]
        blob = ModelRegistry.serialize()
        ModelRegistry.elements.clear()

        self.assertEqual(ModelRegistry.deserialize(blob), 2)
        for element in elements:
            restored = ModelRegistry.elements[element.id]
            self.assertIsNot(restored, element)
            self.assertEqual(restored.description, element.description)

    def test_serialize_given_element_expect_finalize_called_before_pickle(self) -> None:
        element = ModelElement()

        with patch.object(ModelElement, "finalize", autospec=True) as finalize:
            finalize.side_effect = lambda instance: setattr(instance, "description", "finalized")
            blob = ModelRegistry.serialize()

        finalize.assert_called_once_with(element)
        self.assertEqual(pickle.loads(blob)[element.id].description, "finalized")

    def test_serialize_given_failing_element_finalize_expect_error(self) -> None:
        ModelElement()

        with (
            patch.object(ModelElement, "finalize", side_effect=ValueError("invalid element")),
            self.assertRaisesRegex(ValueError, "invalid element"),
        ):
            ModelRegistry.serialize()

    def test_deserialize_detaches_pre_existing_instances(self) -> None:
        original = ModelElement(description="original")
        blob = ModelRegistry.serialize()
        squatter = ModelElement(description="squatter")
        ModelRegistry.elements[original.id] = squatter

        ModelRegistry.deserialize(blob)

        restored = ModelRegistry.elements[original.id]
        self.assertEqual(restored.description, "original")
        self.assertIsNot(restored, original)

    def test_deserialize_drops_elements_absent_from_the_payload(self) -> None:
        blob = ModelRegistry.serialize()
        orphan = ModelElement()

        ModelRegistry.deserialize(blob)

        self.assertNotIn(orphan.id, ModelRegistry.elements)

    def test_malformed_payload_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            ModelRegistry.deserialize(pickle.dumps({"not": "a registry"}))


class TestMerge(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_registry = dict(ModelRegistry.elements)
        ModelRegistry.elements.clear()

    def tearDown(self) -> None:
        ModelRegistry.elements.clear()
        ModelRegistry.elements.update(self._saved_registry)

    def test_merge_given_foreign_registry_expect_elements_added_and_existing_kept(self) -> None:
        foreign = ModelElement(description="foreign")
        foreign_registry = pickle.loads(ModelRegistry.serialize())
        ModelRegistry.elements.clear()
        existing = ModelElement(description="existing")

        added = ModelRegistry.merge(foreign_registry)

        self.assertEqual(added, 1)
        self.assertIs(ModelRegistry.elements[existing.id], existing)
        self.assertEqual(ModelRegistry.elements[foreign.id].description, "foreign")

    def test_merge_given_duplicate_uuid_expect_value_error_and_registry_unchanged(self) -> None:
        existing = ModelElement(description="existing")
        new = ModelElement(description="new")
        foreign_registry = pickle.loads(ModelRegistry.serialize())
        del ModelRegistry.elements[new.id]

        with self.assertRaises(ValueError):
            ModelRegistry.merge(foreign_registry)

        self.assertEqual(ModelRegistry.elements, {existing.id: existing})

    def test_merge_given_invalid_payload_expect_type_error(self) -> None:
        with self.assertRaises(TypeError):
            ModelRegistry.merge({"not": "a registry"})

    def test_merge_serialized_given_partial_model_expect_elements_added_and_existing_kept(self) -> None:
        partial = ModelElement(description="partial")
        blob = ModelRegistry.serialize()
        ModelRegistry.elements.clear()
        existing = ModelElement(description="existing")

        added = ModelRegistry.merge_serialized(blob)

        self.assertEqual(added, 1)
        self.assertIs(ModelRegistry.elements[existing.id], existing)
        self.assertEqual(ModelRegistry.elements[partial.id].description, "partial")

    def test_merge_given_unpickled_child_registry_expect_shared_references_resolvable(self) -> None:
        element = ModelElement(description="child")
        child_result = pickle.dumps({"datatypes": {"child": element}, "registry": ModelRegistry.elements})
        ModelRegistry.elements.clear()

        restored = pickle.loads(child_result)
        ModelRegistry.merge(restored["registry"])

        self.assertIs(restored["datatypes"]["child"], ModelRegistry.elements[element.id])


class TestDatatypeQueries(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_registry = dict(ModelRegistry.elements)
        ModelRegistry.elements.clear()

    def tearDown(self) -> None:
        ModelRegistry.elements.clear()
        ModelRegistry.elements.update(self._saved_registry)

    def test_given_mixed_registry_expect_only_named_datatypes_indexed(self) -> None:
        datatype = StructDataType(name="Value", namespace="example", source_kind=DataTypeSource.PROTOBUF)
        ArrayDataType(data_type=PrimitiveDataType.UINT8, is_inline=True, source_kind=DataTypeSource.PROTOBUF)
        ModelElement()

        result = datatypes_by_name()

        self.assertEqual(result, {"example.Value": datatype})
        self.assertIs(result["example.Value"], datatype)

    def test_given_supplied_elements_expect_registry_untouched(self) -> None:
        first = StructDataType(name="First", source_kind=DataTypeSource.FRANCA)
        second = StructDataType(name="Second", source_kind=DataTypeSource.FRANCA)

        result = datatypes_by_name((first,))

        self.assertEqual(result, {"First": first})
        self.assertIn(second.id, ModelRegistry.elements)

    def test_given_duplicate_name_expect_value_error(self) -> None:
        StructDataType(name="Value", namespace="example", source_kind=DataTypeSource.PROTOBUF)
        StructDataType(name="Value", namespace="example", source_kind=DataTypeSource.PROTOBUF)

        with self.assertRaisesRegex(ValueError, "Duplicate datatype name: example.Value"):
            datatypes_by_name()

    def test_given_duplicate_datatypes_expect_finalize_and_serialize_to_reject_model(self) -> None:
        StructDataType(name="Value", namespace="example", source_kind=DataTypeSource.FRANCA)
        StructDataType(name="Value", namespace="example", source_kind=DataTypeSource.PROTOBUF)

        with self.assertRaisesRegex(ValueError, "Duplicate datatype name: example.Value"):
            ModelRegistry.finalize()
        with self.assertRaisesRegex(ValueError, "Duplicate datatype name: example.Value"):
            ModelRegistry.serialize()

    def test_given_anonymous_types_expect_finalize_to_accept_model(self) -> None:
        ArrayDataType(data_type=PrimitiveDataType.UINT8, is_inline=True, source_kind=DataTypeSource.PROTOBUF)
        ArrayDataType(data_type=PrimitiveDataType.UINT8, is_inline=True, source_kind=DataTypeSource.PROTOBUF)

        ModelRegistry.finalize()
        self.assertEqual(ModelRegistry.deserialize(ModelRegistry.serialize()), 2)


if __name__ == "__main__":
    unittest.main()
