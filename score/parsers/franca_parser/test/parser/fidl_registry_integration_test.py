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

"""Inspect and verify the registry pickle produced by a multi-file FIDL Bazel action."""

import argparse
import json
import unittest
from enum import Enum
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from score.ecu_model.communication.service_interface import InterfaceDefinition
from score.ecu_model.data_types.common import DataTypeBase, DataTypeSource
from score.ecu_model.data_types.identifier import Identifier, QualifiedName, SelectableIdentifier
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.model import ModelElement, ModelRegistry


def encode_value(value: object) -> object:
    """Represent model references by UUID rather than recursively expanding their targets."""
    if isinstance(value, ModelElement):
        return {"$ref": str(value.id)}
    if isinstance(value, (Identifier, QualifiedName, SelectableIdentifier, UUID)):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return {name: encode_value(getattr(value, name)) for name in type(value).model_fields}
    if isinstance(value, dict):
        return {str(key): encode_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported registry field value: {type(value).__name__}")


def registry_document() -> dict[str, object]:
    """Describe every registered object, including its fields and graph references."""
    elements = {}
    for element in sorted(
        ModelRegistry.elements.values(),
        key=lambda item: (type(item).__name__, str(getattr(item, "name", "")), str(item.id)),
    ):
        entry = {
            "type": type(element).__name__,
            "fields": {name: encode_value(getattr(element, name)) for name in type(element).model_fields},
        }
        if isinstance(element, (DataTypeBase, InterfaceDefinition)) and element.name is not None:
            entry["fully_qualified_name"] = element.fully_qualified_name
        elements[str(element.id)] = entry
    return {"schema_version": 1, "element_count": len(elements), "elements": elements}


class FIDLRegistryIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(__file__).parent
        ModelRegistry.deserialize((directory / "fidl_integration_model.pkl").read_bytes())
        self.document = json.loads((directory / "fidl_integration_model.json").read_text(encoding="utf-8"))
        self.datatypes = {
            element.fully_qualified_name: element
            for element in ModelRegistry.elements.values()
            if isinstance(element, DataTypeBase) and element.name is not None
        }
        self.interfaces = {
            element.fully_qualified_name: element
            for element in ModelRegistry.elements.values()
            if isinstance(element, InterfaceDefinition)
        }

    def tearDown(self) -> None:
        ModelRegistry.elements.clear()

    def test_pickle_preserves_cross_file_and_circular_references(self) -> None:
        self.assertEqual(set(self.interfaces), {"integration.service.Catalog", "integration.events.Notifications"})
        payload = self.datatypes["integration.common.CommonTypes.Payload"]
        request = self.datatypes["integration.service.ServiceTypes.Request"]
        envelope = self.datatypes["integration.service.ServiceTypes.Envelope"]
        event = self.datatypes["integration.events.EventTypes.Event"]
        request_id = self.datatypes["integration.common.RequestId"]
        self.assertEqual(len(self.datatypes), 14)
        self.assertIs(payload.fields[0].data_type, request_id)
        self.assertIs(request.fields[0].data_type, request_id)
        self.assertIs(request.fields[1].data_type, payload)
        self.assertIs(envelope.fields[0].data_type, request)
        self.assertIs(envelope.fields[1].data_type, event)
        self.assertIs(event.fields[0].data_type, payload)
        self.assertIs(event.fields[1].data_type, envelope)
        self.assertIs(request_id.data_type, PrimitiveDataType.UINT64)
        for datatype in self.datatypes.values():
            self.assertEqual(datatype.source_kind, DataTypeSource.FRANCA)
            self.assertIn(Path(datatype.source_uri).name, {"common.fidl", "service.fidl", "events.fidl"})
            self.assertIs(ModelRegistry.elements[datatype.id], datatype)

    def test_pickle_preserves_interface_members_and_datatype_details(self) -> None:
        catalog = self.interfaces["integration.service.Catalog"]
        self.assertEqual((catalog.version.major, catalog.version.minor, catalog.version.patch), (2, 3, 0))
        self.assertIn("Integration service", catalog.description)
        result = self.datatypes["integration.service.Catalog.Result"]
        results = self.datatypes["integration.service.Catalog.Results"]
        label = self.datatypes["integration.service.Catalog.LocalLabel"]
        self.assertIs(result.fields[1].data_type, label)
        self.assertIs(label.data_type, self.datatypes["integration.common.CommonTypes.Label"])
        self.assertIs(results.data_type, result)
        self.assertEqual((results.dimension_min, results.dimension_max), (0, 8))
        query = catalog.methods[SelectableIdentifier("query:byId")]
        self.assertIs(query.inputs[0].data_type, self.datatypes["integration.service.ServiceTypes.Request"])
        self.assertIs(query.outputs[0].data_type, results)
        self.assertIs(query.error_return_codes, self.datatypes["integration.service.Catalog.Errors"])
        index = self.datatypes["integration.common.CommonTypes.PayloadByLabel"]
        self.assertIs(query.outputs[1].data_type, index)
        self.assertIs(index.key_type, self.datatypes["integration.common.CommonTypes.Label"])
        self.assertIs(index.value_type, self.datatypes["integration.common.CommonTypes.Payload"])
        self.assertEqual(len(catalog.methods), 3)
        by_label = catalog.methods[SelectableIdentifier("query:byLabel")]
        self.assertIs(by_label.inputs[0].data_type, label)
        payloads = self.datatypes["integration.common.CommonTypes.Payloads"]
        self.assertIs(by_label.outputs[0].data_type, payloads)
        self.assertIs(payloads.data_type, self.datatypes["integration.common.CommonTypes.Payload"])
        self.assertEqual((payloads.dimension_min, payloads.dimension_max), (0, 16))
        notify = catalog.methods[SelectableIdentifier("notify")]
        self.assertTrue(notify.fire_and_forget)
        self.assertEqual(notify.outputs, [])
        self.assertIsNone(notify.error_return_codes)
        changed = catalog.broadcasts[SelectableIdentifier("changed")]
        self.assertTrue(changed.selective)
        self.assertIs(changed.outputs[0].data_type, self.datatypes["integration.events.EventTypes.Event"])
        latest = catalog.attributes[Identifier("latest")]
        self.assertIs(latest.data_type, result)
        self.assertTrue(latest.has_getter)
        self.assertFalse(latest.has_setter)
        self.assertTrue(latest.subscribable)
        cached = catalog.attributes[Identifier("cached")]
        self.assertFalse(cached.has_getter)
        self.assertTrue(cached.has_setter)
        self.assertFalse(cached.subscribable)
        self.assertTrue(cached.data_type.is_inline)
        self.assertIs(cached.data_type.data_type, self.datatypes["integration.common.CommonTypes.Payload"])
        self.assertEqual((cached.data_type.dimension_min, cached.data_type.dimension_max), (0, 4))
        status = self.datatypes["integration.common.CommonTypes.Status"]
        self.assertEqual(
            [(value.name.as_str, value.value) for value in status.values],
            [("UNKNOWN", 0), ("READY", 16), ("FAILED", 17)],
        )
        value = self.datatypes["integration.common.CommonTypes.Value"]
        self.assertIs(value.fields[1].data_type, self.datatypes["integration.common.CommonTypes.Label"])
        notifications = self.interfaces["integration.events.Notifications"]
        self.assertEqual((notifications.version.major, notifications.version.minor), (1, 2))
        received = notifications.broadcasts[SelectableIdentifier("received")]
        self.assertIs(received.outputs[0].data_type, self.datatypes["integration.events.EventTypes.Event"])
        state = notifications.attributes[Identifier("state")]
        self.assertIs(state.data_type, status)
        self.assertFalse(state.has_setter)
        self.assertFalse(state.subscribable)

    def test_json_describes_the_exact_pickle_registry(self) -> None:
        self.assertEqual(self.document, registry_document())
        elements = self.document["elements"]
        self.assertEqual(set(elements), {str(identifier) for identifier in ModelRegistry.elements})

        def check_references(value: object) -> None:
            if isinstance(value, dict):
                if "$ref" in value:
                    self.assertIn(value["$ref"], elements)
                for item in value.values():
                    check_references(item)
            elif isinstance(value, list):
                for item in value:
                    check_references(item)

        check_references(self.document)


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--pickle")
    argument_parser.add_argument("--json")
    arguments, test_arguments = argument_parser.parse_known_args()
    if arguments.pickle or arguments.json:
        if not arguments.pickle or not arguments.json:
            argument_parser.error("--pickle and --json must be supplied together")
        ModelRegistry.deserialize(Path(arguments.pickle).read_bytes())
        Path(arguments.json).write_text(json.dumps(registry_document(), indent=2) + "\n", encoding="utf-8")
    else:
        unittest.main(argv=[__file__, *test_arguments])
