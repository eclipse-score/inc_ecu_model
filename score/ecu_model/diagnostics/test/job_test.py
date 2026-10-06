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
from score.ecu_model.communication.binding import CommunicationBinding, NetworkKind, ProtocolKind
from score.ecu_model.communication.service_interface import InterfaceDefinition, Method, ServiceInterface
from score.ecu_model.communication.service_port import ProvidedServicePort
from score.ecu_model.diagnostics.job import DiagnosticJob, DiagnosticJobBinding, DiagnosticServiceType
from score.ecu_model.model import ModelRegistry


class TestDiagnosticJob(unittest.TestCase):
    def setUp(self) -> None:
        ModelRegistry.elements.clear()

    def _interface(self, name: str = "VehicleSpeedInterface") -> InterfaceDefinition:
        return InterfaceDefinition(
            name=name,
            version=Version(),
            methods={"Read": Method(name="Read"), "Cancel": Method(name="Cancel")},
        )

    def _provided_port(self, interface: InterfaceDefinition) -> ProvidedServicePort:
        return ProvidedServicePort(
            name="VehicleSpeedProvider",
            interface=ServiceInterface(
                name="VehicleSpeedDeployment",
                design_element=interface,
                method_deployment_properties={"Read": {}, "Cancel": {}},
            ),
            binding=CommunicationBinding(protocol=ProtocolKind.ARA_COM, network=NetworkKind.SOMEIP),
        )

    def test_job_binding_accepts_port_providing_the_job_interface(self) -> None:
        interface = self._interface()
        job = DiagnosticJob(
            name="VehicleSpeed",
            interface=interface,
            service_type=DiagnosticServiceType.READ_DATA_BY_IDENTIFIER,
            service_id=0x6F07,
        )
        service_port = self._provided_port(interface)

        binding = DiagnosticJobBinding(diagnostic_job=job, service_port=service_port)

        self.assertIs(binding.diagnostic_job, job)
        self.assertIs(binding.service_port, service_port)

    def test_job_binding_rejects_port_providing_another_interface(self) -> None:
        job = DiagnosticJob(
            name="VehicleSpeed",
            interface=self._interface(),
            service_type=DiagnosticServiceType.READ_DATA_BY_IDENTIFIER,
            service_id=0x6F07,
        )

        with self.assertRaises(ValidationError):
            DiagnosticJobBinding(diagnostic_job=job, service_port=self._provided_port(self._interface("VehicleState")))

    def test_job_rejects_service_id_outside_16_bit_range(self) -> None:
        with self.assertRaises(ValidationError):
            DiagnosticJob(
                name="VehicleSpeed",
                interface=self._interface(),
                service_type=DiagnosticServiceType.READ_DATA_BY_IDENTIFIER,
                service_id=0x10000,
            )

    def test_job_rejects_blank_deployment_property_names(self) -> None:
        with self.assertRaises(ValidationError):
            DiagnosticJob(
                name="VehicleSpeed",
                interface=self._interface(),
                service_type=DiagnosticServiceType.READ_DATA_BY_IDENTIFIER,
                service_id=0x6F07,
                deployment_properties={"  ": "value"},
            )


if __name__ == "__main__":
    unittest.main()
