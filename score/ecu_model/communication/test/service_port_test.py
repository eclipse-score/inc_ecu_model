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
from score.ecu_model.communication.protocol import ProtocolKind
from score.ecu_model.communication.service_interface import (
    InterfaceDefinition,
    ServiceInterface,
)
from score.ecu_model.communication.service_port import (
    ProvidedServicePort,
    RequiredServicePort,
)
from score.ecu_model.communication.detail.service_port import PortDefinition
from score.ecu_model.model import ModelRegistry


class TestServicePort(unittest.TestCase):
    def setUp(self) -> None:
        ModelRegistry.elements.clear()

    def _service_interface(self, design_element: InterfaceDefinition | None = None) -> ServiceInterface:
        return ServiceInterface(
            name="VehicleStateDeployment",
            namespace="deployment",
            design_element=design_element or InterfaceDefinition(name="VehicleState", version=Version()),
            service_id=42,
        )

    def test_provided_port_preserves_service_metadata(self) -> None:
        service_interface = self._service_interface()
        port = ProvidedServicePort(
            name="VehicleStateProvider",
            interface=service_interface,
            instance_id=7,
            protocol=ProtocolKind.ARA_COM,
            deployment_properties={"port_id": 1},
        )

        self.assertIsInstance(port, ProvidedServicePort)
        self.assertIs(port.interface, service_interface)
        self.assertEqual(port.instance_id, 7)
        self.assertEqual(port.deployment_properties, {"port_id": 1})

    def test_required_port_preserves_interface(self) -> None:
        port = RequiredServicePort(
            name="VehicleStateConsumer",
            interface=self._service_interface(),
            protocol=ProtocolKind.MW_COM,
        )

        self.assertIsInstance(port, RequiredServicePort)

    def test_port_specification_instantiation_and_registration(self) -> None:
        design = InterfaceDefinition(name="VehicleState", version=Version())
        design_element = PortDefinition(
            interface_design=design,
            description="Speed port specification",
        )

        self.assertIs(design_element.interface_design, design)
        self.assertEqual(design_element.description, "Speed port specification")
        self.assertIs(ModelRegistry.elements[design_element.id], design_element)

    def test_required_port_with_matching_port_spec_succeeds(self) -> None:
        design = InterfaceDefinition(name="VehicleState", version=Version())
        service_interface = self._service_interface(design_element=design)
        design_element = PortDefinition(interface_design=design)

        port = RequiredServicePort(
            name="VehicleStateConsumer",
            interface=service_interface,
            design_element=design_element,
            protocol=ProtocolKind.ARA_DIAG,
        )

        self.assertIs(port.design_element, design_element)

    def test_required_port_with_mismatched_port_spec_raises(self) -> None:
        design_a = InterfaceDefinition(name="VehicleStateA", version=Version())
        design_b = InterfaceDefinition(name="VehicleStateB", version=Version())
        service_interface = self._service_interface(design_element=design_a)
        design_element = PortDefinition(interface_design=design_b)

        with self.assertRaises(ValidationError):
            RequiredServicePort(
                name="VehicleStateConsumer",
                interface=service_interface,
                design_element=design_element,
                protocol=ProtocolKind.ARA_DIAG,
            )

    def test_instance_id_must_be_positive_integer(self) -> None:
        with self.assertRaises(ValidationError):
            ProvidedServicePort(
                name="VehicleStateProvider",
                interface=self._service_interface(),
                instance_id=0,
                protocol=ProtocolKind.MW_DIAG,
            )

    def test_deployment_property_names_must_not_be_empty(self) -> None:
        with self.assertRaises(ValidationError):
            ProvidedServicePort(
                name="VehicleStateProvider",
                interface=self._service_interface(),
                protocol=ProtocolKind.ARA_COM,
                deployment_properties={" ": True},
            )


if __name__ == "__main__":
    unittest.main()
