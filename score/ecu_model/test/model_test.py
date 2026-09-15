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
from uuid import UUID, uuid4

from pydantic import ValidationError

from score.ecu_model.model import ModelElement, ModelRegistry
from score.ecu_model.data_types.enum import EnumValue


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
        elements = [
            ModelElement(description="first"),
            ModelElement(description="second"),
            EnumValue(description="third"),
        ]
        blob = ModelRegistry.serialize()
        ModelRegistry.elements.clear()

        self.assertEqual(ModelRegistry.deserialize(blob), 2)
        for element in elements:
            restored = ModelRegistry.elements[element.id]
            self.assertIsNot(restored, element)
            self.assertEqual(restored.description, element.description)

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


if __name__ == "__main__":
    unittest.main()
