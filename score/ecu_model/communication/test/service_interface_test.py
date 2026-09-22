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
    AttributeBinding,
    Broadcast,
    BroadcastBinding,
    InterfaceDefinition,
    Method,
    MethodBinding,
    ServiceInterface,
)
from score.ecu_model.model import ModelRegistry


class TestServiceInterface(unittest.TestCase):
    def setUp(self) -> None:
        ModelRegistry.elements.clear()

    def test_service_interface_preserves_design_members_and_bindings(self) -> None:
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
            broadcast_bindings={"VehicleStateChanged": BroadcastBinding(deployment_properties={"event_id": 1})},
            attribute_bindings={"CurrentVehicleState": AttributeBinding(deployment_properties={"field_id": 2})},
            method_bindings={"Reset": MethodBinding(deployment_properties={"method_id": 3})},
        )

        self.assertEqual(design.fully_qualified_name, "example.VehicleState")
        self.assertIs(service_interface.design_element, design)
        self.assertEqual(service_interface.service_id, 42)

    def test_bindings_must_reference_declared_members(self) -> None:
        with self.assertRaises(ValidationError):
            ServiceInterface(
                name="VehicleStateDeployment",
                design_element=InterfaceDefinition(
                    name="VehicleState",
                    version=Version(),
                ),
                broadcast_bindings={"Unknown": BroadcastBinding()},
            )

    def test_bindings_must_cover_all_declared_members(self) -> None:
        with self.assertRaises(ValidationError):
            ServiceInterface(
                name="VehicleStateDeployment",
                design_element=InterfaceDefinition(
                    name="VehicleState",
                    version=Version(),
                    broadcasts={"VehicleStateChanged": Broadcast(name="VehicleStateChanged")},
                ),
            )

    def test_attribute_bindings_must_reference_declared_attributes(self) -> None:
        with self.assertRaises(ValidationError):
            ServiceInterface(
                name="VehicleStateDeployment",
                design_element=InterfaceDefinition(
                    name="VehicleState",
                    version=Version(),
                ),
                attribute_bindings={"Unknown": AttributeBinding()},
            )

    def test_method_bindings_must_reference_declared_methods(self) -> None:
        with self.assertRaises(ValidationError):
            ServiceInterface(
                name="VehicleStateDeployment",
                design_element=InterfaceDefinition(
                    name="VehicleState",
                    version=Version(),
                ),
                method_bindings={"Unknown": MethodBinding()},
            )

    def test_attribute_bindings_must_cover_all_declared_attributes(self) -> None:
        with self.assertRaises(ValidationError):
            ServiceInterface(
                name="VehicleStateDeployment",
                design_element=InterfaceDefinition(
                    name="VehicleState",
                    version=Version(),
                    attributes={"CurrentVehicleState": Attribute(name="CurrentVehicleState", data_type="VehicleState")},
                ),
            )

    def test_method_bindings_must_cover_all_declared_methods(self) -> None:
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

    def test_binding_deployment_properties_validation(self) -> None:
        binding = BroadcastBinding(deployment_properties={"event_id": 1})
        self.assertEqual(binding.deployment_properties, {"event_id": 1})

        with self.assertRaises(ValidationError):
            BroadcastBinding(deployment_properties={" ": 1})

        with self.assertRaises(ValidationError):
            AttributeBinding(deployment_properties={"": 1})

        with self.assertRaises(ValidationError):
            MethodBinding(deployment_properties={"   ": 1})

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

    def test_service_id_must_be_a_non_negative_integer(self) -> None:
        with self.assertRaises(ValidationError):
            ServiceInterface(
                name="VehicleStateDeployment",
                design_element=InterfaceDefinition(name="VehicleState", version=Version()),
                service_id=-1,
            )


if __name__ == "__main__":
    unittest.main()
