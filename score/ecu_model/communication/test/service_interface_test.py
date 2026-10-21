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

import unittest

from pydantic import ValidationError

from score.ecu_model.common.version import Version
from score.ecu_model.communication.service_interface import (
    Attribute,
    Broadcast,
    InterfaceDefinition,
    Method,
    ServiceInterface,
)
from score.ecu_model.data_types.identifier import Identifier, SelectableIdentifier
from score.ecu_model.model import ModelRegistry


class TestServiceInterface(unittest.TestCase):
    def setUp(self) -> None:
        ModelRegistry.elements.clear()

    def test_method_descriptions(self) -> None:
        method = Method(name="Query")
        self.assertEqual(method.description, "")
        self.assertEqual(method.error_description, "")
        method.description = "Query a value"
        method.error_description = "The query failed"
        serialized = method.model_dump()
        self.assertEqual(serialized["description"], "Query a value")
        self.assertEqual(serialized["error_description"], "The query failed")

    def test_service_interface_preserves_design_members_and_properties(self) -> None:
        design = InterfaceDefinition(
            name="VehicleState",
            namespace="example",
            version=Version(major=1, minor=0, patch=0),
            broadcasts={"VehicleStateChanged": Broadcast(name="VehicleStateChanged")},
            attributes={"CurrentVehicleState": Attribute(name="CurrentVehicleState", data_type="VehicleState")},
            methods={"Reset": Method(name="Reset")},
        )
        service_interface = ServiceInterface(
            name="VehicleStateDeployment",
            namespace="deployment",
            design_element=design,
            service_id=42,
            broadcast_deployment_properties={"VehicleStateChanged": {"event_id": 1}},
            attribute_deployment_properties={"CurrentVehicleState": {"field_id": 2}},
            method_deployment_properties={"Reset": {"method_id": 3}},
        )

        self.assertEqual(design.fully_qualified_name, "example.VehicleState")
        self.assertIs(service_interface.design_element, design)
        self.assertEqual(service_interface.service_id, 42)

    def test_member_deployment_properties_must_reference_declared_members(self) -> None:
        with self.assertRaises(ValidationError):
            ServiceInterface(
                name="VehicleStateDeployment",
                design_element=InterfaceDefinition(
                    name="VehicleState",
                    version=Version(),
                ),
                broadcast_deployment_properties={"Unknown": {}},
            )

    def test_member_deployment_properties_must_cover_all_declared_members(self) -> None:
        with self.assertRaises(ValidationError):
            ServiceInterface(
                name="VehicleStateDeployment",
                design_element=InterfaceDefinition(
                    name="VehicleState",
                    version=Version(),
                    broadcasts={"VehicleStateChanged": Broadcast(name="VehicleStateChanged")},
                ),
            )

    def test_attribute_deployment_properties_must_reference_declared_attributes(self) -> None:
        with self.assertRaises(ValidationError):
            ServiceInterface(
                name="VehicleStateDeployment",
                design_element=InterfaceDefinition(
                    name="VehicleState",
                    version=Version(),
                ),
                attribute_deployment_properties={"Unknown": {}},
            )

    def test_method_deployment_properties_must_reference_declared_methods(self) -> None:
        with self.assertRaises(ValidationError):
            ServiceInterface(
                name="VehicleStateDeployment",
                design_element=InterfaceDefinition(
                    name="VehicleState",
                    version=Version(),
                ),
                method_deployment_properties={"Unknown": {}},
            )

    def test_attribute_deployment_properties_must_cover_all_declared_attributes(self) -> None:
        with self.assertRaises(ValidationError):
            ServiceInterface(
                name="VehicleStateDeployment",
                design_element=InterfaceDefinition(
                    name="VehicleState",
                    version=Version(),
                    attributes={"CurrentVehicleState": Attribute(name="CurrentVehicleState", data_type="VehicleState")},
                ),
            )

    def test_method_deployment_properties_must_cover_all_declared_methods(self) -> None:
        with self.assertRaises(ValidationError):
            ServiceInterface(
                name="VehicleStateDeployment",
                design_element=InterfaceDefinition(
                    name="VehicleState",
                    version=Version(),
                    methods={"Reset": Method(name="Reset")},
                ),
            )

    def test_member_dictionary_keys_must_match_member_names(self) -> None:
        with self.assertRaises(ValidationError):
            InterfaceDefinition(
                name="VehicleState",
                version=Version(),
                broadcasts={"Changed": Broadcast(name="VehicleStateChanged")},
            )
        with self.assertRaises(ValidationError):
            InterfaceDefinition(
                name="VehicleState",
                version=Version(),
                attributes={"Changed": Attribute(name="CurrentVehicleState", data_type="VehicleState")},
            )
        with self.assertRaises(ValidationError):
            InterfaceDefinition(
                name="VehicleState",
                version=Version(),
                methods={"Changed": Method(name="Reset")},
            )

    def test_attribute_and_method_defaults(self) -> None:
        attr = Attribute(name="Speed", data_type="SpeedData")
        self.assertTrue(attr.has_getter)
        self.assertTrue(attr.has_setter)
        self.assertTrue(attr.subscribable)

        method = Method(name="Reset")
        self.assertEqual(method.inputs, [])
        self.assertEqual(method.outputs, [])
        self.assertIsNone(method.error_return_codes)
        self.assertFalse(method.fire_and_forget)

    def test_overloads_preserve_names_and_deployment_identity(self) -> None:
        first = SelectableIdentifier("Query:first")
        second = SelectableIdentifier("Query:second")
        design = InterfaceDefinition(
            name="API",
            version=Version(),
            methods={first: Method(name=first), second: Method(name=second)},
        )
        deployment = ServiceInterface(
            name="Deployment",
            design_element=design,
            method_deployment_properties={"Query:first": {}, "Query:second": {}},
        )
        self.assertEqual(design.methods[first].name.as_str, "Query:first")
        self.assertEqual(set(deployment.method_deployment_properties), {first, second})
        with self.assertRaises(ValidationError):
            ServiceInterface(name="Incomplete", design_element=design, method_deployment_properties={"Query": {}})

    def test_interface_has_no_inheritance_api(self) -> None:
        design = InterfaceDefinition(name="API", version=Version())
        self.assertNotIn("base", InterfaceDefinition.model_fields)
        for attribute in ("all_methods", "all_broadcasts", "all_attributes", "all_datatypes"):
            self.assertFalse(hasattr(design, attribute))
        ServiceInterface(name="Deployment", design_element=design)
        with self.assertRaises(ValidationError):
            ServiceInterface(name="Deployment", design_element=design, method_deployment_properties={"Ping": {}})

    def test_member_identity_must_match_selector_as_well_as_name(self) -> None:
        with self.assertRaises(ValidationError):
            InterfaceDefinition(name="API", version=Version(), methods={"Query:first": Method(name="Query:second")})
        identity = SelectableIdentifier("Changed:first")
        design = InterfaceDefinition(name="API", version=Version(), broadcasts={identity: Broadcast(name=identity)})
        ServiceInterface(name="Deployment", design_element=design, broadcast_deployment_properties={identity: {}})

    def test_deployment_properties_validation(self) -> None:
        service_interface = ServiceInterface(
            name="VehicleStateDeployment",
            design_element=InterfaceDefinition(name="VehicleState", version=Version()),
            deployment_properties={"event_id": 1},
        )
        self.assertEqual(service_interface.deployment_properties, {"event_id": 1})

        with self.assertRaises(ValidationError):
            ServiceInterface(
                name="VehicleStateDeployment",
                design_element=InterfaceDefinition(name="VehicleState", version=Version()),
                deployment_properties={" ": 1},
            )

        with self.assertRaises(ValidationError):
            ServiceInterface(
                name="VehicleStateDeployment",
                design_element=InterfaceDefinition(name="VehicleState", version=Version()),
                broadcast_deployment_properties={"VehicleStateChanged": {" ": 1}},
            )

    def test_service_interface_with_string_namespace_and_properties(self) -> None:
        design = InterfaceDefinition(name="VehicleState", version=Version())
        service_interface = ServiceInterface(
            name="VehicleStateDeployment",
            namespace="deployment.sub",
            design_element=design,
            deployment_properties={"timeout_ms": 100},
        )
        self.assertEqual(service_interface.namespace.as_str, "deployment.sub")
        self.assertEqual(service_interface.deployment_properties, {"timeout_ms": 100})

    def test_deployment_property_names_must_not_be_empty(self) -> None:
        with self.assertRaises(ValidationError):
            ServiceInterface(
                name="VehicleStateDeployment",
                design_element=InterfaceDefinition(name="VehicleState", version=Version()),
                deployment_properties={" ": "invalid"},
            )

    def test_members_store_names_without_identity_or_selector_fields(self) -> None:
        for member in (
            Method(name="Query:first"),
            Broadcast(name="Changed:first"),
            Attribute(name="Speed", data_type="SpeedData"),
        ):
            with self.subTest(member=type(member).__name__):
                self.assertIn("name", type(member).model_fields)
                self.assertNotIn("identity", type(member).model_fields)
                self.assertNotIn("selector", type(member).model_fields)
                name_type = Identifier if isinstance(member, Attribute) else SelectableIdentifier
                self.assertIsInstance(member.name, name_type)
                member.name = "Renamed"
                self.assertEqual(member.name, name_type("Renamed"))
                with self.assertRaises(ValidationError):
                    member.name.root = "Mutated"

    def test_attribute_selectors_are_rejected_on_creation_and_assignment(self) -> None:
        with self.assertRaises(ValidationError):
            Attribute(name="Speed:invalid", data_type="SpeedData")
        attribute = Attribute(name="Speed", data_type="SpeedData")
        with self.assertRaises(ValidationError):
            attribute.name = "Speed:invalid"
        self.assertEqual(attribute.name, Identifier("Speed"))

    def test_registry_round_trip_preserves_member_identities_and_references(self) -> None:
        method = Method(name="Query:first")
        broadcast = Broadcast(name="Changed:first")
        attribute = Attribute(name="Speed", data_type="SpeedData")
        design = InterfaceDefinition(
            name="API",
            version=Version(),
            methods={method.name: method},
            broadcasts={broadcast.name: broadcast},
            attributes={attribute.name: attribute},
        )
        deployment = ServiceInterface(
            name="Deployment",
            design_element=design,
            method_deployment_properties={method.name: {}},
            broadcast_deployment_properties={broadcast.name: {}},
            attribute_deployment_properties={attribute.name: {}},
        )
        serialized = ModelRegistry.serialize()
        ModelRegistry.elements.clear()
        self.assertEqual(ModelRegistry.deserialize(serialized), 5)
        restored_design = ModelRegistry.elements[design.id]
        restored_deployment = ModelRegistry.elements[deployment.id]
        self.assertIs(restored_deployment.design_element, restored_design)
        for members, properties, original in (
            (restored_design.methods, restored_deployment.method_deployment_properties, method),
            (restored_design.broadcasts, restored_deployment.broadcast_deployment_properties, broadcast),
            (restored_design.attributes, restored_deployment.attribute_deployment_properties, attribute),
        ):
            with self.subTest(member=type(original).__name__):
                lookup = type(original.name)(original.name.as_str)
                restored_member = members[lookup]
                self.assertIs(restored_member, ModelRegistry.elements[original.id])
                self.assertIs(next(iter(members)), restored_member.name)
                self.assertIn(lookup, properties)

    def test_service_id_must_be_a_non_negative_integer(self) -> None:
        with self.assertRaises(ValidationError):
            ServiceInterface(
                name="VehicleStateDeployment",
                design_element=InterfaceDefinition(name="VehicleState", version=Version()),
                service_id=-1,
            )


if __name__ == "__main__":
    unittest.main()
