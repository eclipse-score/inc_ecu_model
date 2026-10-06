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

from score.ecu_model.architecture.activity import Activity
from score.ecu_model.architecture.application import Application
from score.ecu_model.common.version import Version
from score.ecu_model.communication.binding import CommunicationBinding, NetworkKind, ProtocolKind
from score.ecu_model.communication.service_interface import InterfaceDefinition, Method, ServiceInterface
from score.ecu_model.communication.service_port import ProvidedServicePort, RequiredServicePort
from score.ecu_model.data_types.identifier import QualifiedName
from score.ecu_model.diagnostics.dtc import DiagnosticTroubleCode, DtcServiceBinding
from score.ecu_model.diagnostics.job import DiagnosticJob, DiagnosticJobBinding, DiagnosticServiceType
from score.ecu_model.model import ModelRegistry


class TestApplication(unittest.TestCase):
    def setUp(self) -> None:
        ModelRegistry.elements.clear()

    def _activity(self, name: str = "SpeedLimiter") -> Activity:
        return Activity(name=name)

    def _service_port(self) -> ProvidedServicePort:
        return ProvidedServicePort(
            name="VehicleStateProvider",
            interface=ServiceInterface(
                name="VehicleStateDeployment",
                namespace="deployment",
                design_element=InterfaceDefinition(name="VehicleState", version=Version()),
                service_id=42,
            ),
            binding=CommunicationBinding(protocol=ProtocolKind.ARA_COM, network=NetworkKind.SOMEIP),
        )

    def _required_service_port(self) -> RequiredServicePort:
        return RequiredServicePort(
            name="VehicleStateConsumer",
            interface=ServiceInterface(
                name="VehicleStateDeployment",
                namespace="deployment",
                design_element=InterfaceDefinition(name="VehicleState", version=Version()),
                service_id=43,
            ),
            binding=CommunicationBinding(protocol=ProtocolKind.ARA_COM, network=NetworkKind.SOMEIP),
        )

    def test_application_groups_activities_and_service_ports(self) -> None:
        activity = self._activity()
        service_port = self._service_port()
        application = Application(
            name="DrivingApp",
            namespace=QualifiedName(("adp", "driving")),
            description="Longitudinal driving application",
            activities=[activity],
            provided_service_ports=[service_port],
            deployment_properties={"machine": "adp"},
        )

        self.assertEqual(application.name.as_str, "DrivingApp")
        self.assertEqual(application.fully_qualified_name, "adp.driving.DrivingApp")
        self.assertIs(application.activities[0], activity)
        self.assertIs(application.provided_service_ports[0], service_port)
        self.assertEqual(application.required_service_ports, [])
        self.assertEqual(application.deployment_properties, {"machine": "adp"})

    def test_application_requires_at_least_one_activity(self) -> None:
        with self.assertRaises(ValidationError):
            Application(name="DrivingApp", activities=[])

    def test_application_rejects_duplicate_activity_names(self) -> None:
        with self.assertRaises(ValidationError):
            Application(
                name="DrivingApp",
                activities=[self._activity(), self._activity()],
            )

    def test_application_rejects_blank_deployment_property_names(self) -> None:
        with self.assertRaises(ValidationError):
            Application(
                name="DrivingApp",
                activities=[self._activity()],
                deployment_properties={"  ": "value"},
            )

    def test_application_rejects_diagnostic_binding_to_unrequired_port(self) -> None:
        with self.assertRaises(ValidationError):
            Application(
                name="DrivingApp",
                activities=[self._activity()],
                diagnostic_bindings=[
                    DtcServiceBinding(
                        trouble_code=DiagnosticTroubleCode(trouble_code=0x7F9184),
                        required_service_port=self._required_service_port(),
                        diagnostic_event_name="VehicleStateFailure",
                        diagnostic_event_instance_id=33764,
                    )
                ],
            )

    def test_application_offers_ecu_job_through_provided_port(self) -> None:
        vehicle_speed_interface = InterfaceDefinition(
            name="VehicleSpeedInterface",
            version=Version(),
            methods={"Read": Method(name="Read"), "Cancel": Method(name="Cancel")},
        )
        service_port = ProvidedServicePort(
            name="VehicleSpeedProvider",
            interface=ServiceInterface(
                name="VehicleSpeedDeployment",
                design_element=vehicle_speed_interface,
                method_deployment_properties={"Read": {}, "Cancel": {}},
            ),
            binding=CommunicationBinding(protocol=ProtocolKind.ARA_COM, network=NetworkKind.SOMEIP),
        )
        job = DiagnosticJob(
            name="VehicleSpeed",
            interface=vehicle_speed_interface,
            service_type=DiagnosticServiceType.READ_DATA_BY_IDENTIFIER,
            service_id=0x6F07,
        )
        job_binding = DiagnosticJobBinding(diagnostic_job=job, service_port=service_port)

        application = Application(
            name="DrivingApp",
            activities=[self._activity()],
            provided_service_ports=[service_port],
            diagnostic_job_bindings=[job_binding],
        )

        self.assertIs(application.diagnostic_job_bindings[0].diagnostic_job, job)
        self.assertIs(application.diagnostic_job_bindings[0].service_port, service_port)


if __name__ == "__main__":
    unittest.main()
