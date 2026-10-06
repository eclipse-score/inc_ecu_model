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
from score.ecu_model.architecture.ecu import Ecu
from score.ecu_model.common.version import Version
from score.ecu_model.communication.binding import CommunicationBinding, NetworkKind, ProtocolKind
from score.ecu_model.communication.service_interface import InterfaceDefinition, Method, ServiceInterface
from score.ecu_model.communication.service_port import ProvidedServicePort, RequiredServicePort
from score.ecu_model.data_types.identifier import QualifiedName
from score.ecu_model.diagnostics.dtc import DiagnosticTroubleCode, DtcServiceBinding
from score.ecu_model.diagnostics.job import DiagnosticJob, DiagnosticJobBinding, DiagnosticServiceType
from score.ecu_model.model import ModelRegistry


class TestEcu(unittest.TestCase):
    def setUp(self) -> None:
        ModelRegistry.elements.clear()

    def _application(self, name: str = "DrivingApp") -> Application:
        return Application(name=name, activities=[Activity(name="SpeedLimiter")])

    def _application_with_diagnostic_binding(
        self,
        trouble_code: DiagnosticTroubleCode,
        name: str = "DrivingApp",
        event_name: str = "VehicleStateFailure",
        event_instance_id: int = 33764,
    ) -> tuple[Application, RequiredServicePort]:
        required_port = RequiredServicePort(
            name="VehicleStateConsumer",
            interface=ServiceInterface(
                name="VehicleStateDeployment",
                namespace="deployment",
                design_element=InterfaceDefinition(name="VehicleState", version=Version()),
            ),
            binding=CommunicationBinding(protocol=ProtocolKind.ARA_COM, network=NetworkKind.SOMEIP),
        )
        application = Application(
            name=name,
            activities=[Activity(name="SpeedLimiter")],
            required_service_ports=[required_port],
            diagnostic_bindings=[
                DtcServiceBinding(
                    trouble_code=trouble_code,
                    required_service_port=required_port,
                    diagnostic_event_name=event_name,
                    diagnostic_event_instance_id=event_instance_id,
                )
            ],
        )
        return application, required_port

    def _diagnostic_job(
        self,
        job_name: str = "VehicleSpeed",
        service_id: int = 0x6F07,
        service_type: DiagnosticServiceType = DiagnosticServiceType.READ_DATA_BY_IDENTIFIER,
    ) -> tuple[DiagnosticJob, DiagnosticJobBinding]:
        job_interface = InterfaceDefinition(
            name=f"{job_name}Interface",
            version=Version(),
            methods={"Read": Method(name="Read"), "Cancel": Method(name="Cancel")},
        )
        service_port = ProvidedServicePort(
            name=f"{job_name}Provider",
            interface=ServiceInterface(
                name=f"{job_name}Deployment",
                design_element=job_interface,
                method_deployment_properties={"Read": {}, "Cancel": {}},
            ),
            binding=CommunicationBinding(protocol=ProtocolKind.ARA_COM, network=NetworkKind.SOMEIP),
        )
        job = DiagnosticJob(
            name=job_name,
            interface=job_interface,
            service_type=service_type,
            service_id=service_id,
        )
        return job, DiagnosticJobBinding(diagnostic_job=job, service_port=service_port)

    def test_ecu_groups_applications(self) -> None:
        application = self._application()
        ecu = Ecu(
            name="AdpEcu",
            namespace=QualifiedName(("adp", "platform")),
            description="Automated driving platform ECU",
            applications=[application],
            deployment_properties={"variant": "high"},
        )

        self.assertEqual(ecu.name.as_str, "AdpEcu")
        self.assertEqual(ecu.fully_qualified_name, "adp.platform.AdpEcu")
        self.assertIs(ecu.applications[0], application)
        self.assertEqual(ecu.deployment_properties, {"variant": "high"})

    def test_ecu_defaults(self) -> None:
        ecu = Ecu(name="AdpEcu", applications=[self._application()])

        self.assertEqual(ecu.fully_qualified_name, "AdpEcu")
        self.assertEqual(ecu.deployment_properties, {})

    def test_ecu_requires_at_least_one_application(self) -> None:
        with self.assertRaises(ValidationError):
            Ecu(name="AdpEcu", applications=[])

    def test_ecu_rejects_duplicate_application_names(self) -> None:
        with self.assertRaises(ValidationError):
            Ecu(name="AdpEcu", applications=[self._application(), self._application()])

    def test_ecu_accepts_applications_with_equal_names_in_different_namespaces(self) -> None:
        driving = Application(
            name="DrivingApp",
            namespace=QualifiedName(("adp", "driving")),
            activities=[Activity(name="SpeedLimiter")],
        )
        parking = Application(
            name="DrivingApp",
            namespace=QualifiedName(("adp", "parking")),
            activities=[Activity(name="SlotFinder")],
        )

        ecu = Ecu(name="AdpEcu", applications=[driving, parking])

        self.assertEqual(len(ecu.applications), 2)

    def test_ecu_rejects_blank_deployment_property_names(self) -> None:
        with self.assertRaises(ValidationError):
            Ecu(name="AdpEcu", applications=[self._application()], deployment_properties={"  ": "value"})

    def test_ecu_rejects_duplicate_diagnostic_trouble_codes(self) -> None:
        with self.assertRaises(ValidationError):
            Ecu(
                name="AdpEcu",
                applications=[self._application()],
                diagnostic_trouble_codes=[
                    DiagnosticTroubleCode(trouble_code=0x7F9184),
                    DiagnosticTroubleCode(trouble_code=0x7F9184),
                ],
            )

    def test_ecu_rejects_diagnostic_binding_to_unknown_trouble_code(self) -> None:
        application, _ = self._application_with_diagnostic_binding(DiagnosticTroubleCode(trouble_code=0x7F9184))

        with self.assertRaises(ValidationError):
            Ecu(name="AdpEcu", applications=[application])

    def test_ecu_accepts_diagnostic_binding_to_required_service_port(self) -> None:
        trouble_code = DiagnosticTroubleCode(trouble_code=0x7F9184)
        application, required_port = self._application_with_diagnostic_binding(trouble_code)

        ecu = Ecu(
            name="AdpEcu",
            applications=[application],
            diagnostic_trouble_codes=[trouble_code],
        )

        binding = ecu.applications[0].diagnostic_bindings[0]
        self.assertIs(binding.trouble_code, trouble_code)
        self.assertIs(binding.required_service_port, required_port)
        self.assertEqual(binding.diagnostic_event_instance_id, 33764)

    def test_ecu_accepts_several_events_for_one_trouble_code(self) -> None:
        trouble_code = DiagnosticTroubleCode(trouble_code=0xED5100)
        first_application, _ = self._application_with_diagnostic_binding(
            trouble_code, name="BrakeApp", event_name="EgoMotionInvalidBrakeApp", event_instance_id=62206
        )
        second_application, _ = self._application_with_diagnostic_binding(
            trouble_code, name="PowertrainApp", event_name="EgoMotionInvalidPowertrainApp", event_instance_id=62236
        )

        ecu = Ecu(
            name="AdpEcu",
            applications=[first_application, second_application],
            diagnostic_trouble_codes=[trouble_code],
        )

        self.assertIs(ecu.applications[0].diagnostic_bindings[0].trouble_code, trouble_code)
        self.assertIs(ecu.applications[1].diagnostic_bindings[0].trouble_code, trouble_code)

    def test_ecu_rejects_duplicate_diagnostic_event_names(self) -> None:
        trouble_code = DiagnosticTroubleCode(trouble_code=0xED5100)
        first_application, _ = self._application_with_diagnostic_binding(
            trouble_code, name="BrakeApp", event_name="EgoMotionInvalid", event_instance_id=62206
        )
        second_application, _ = self._application_with_diagnostic_binding(
            trouble_code, name="PowertrainApp", event_name="EgoMotionInvalid", event_instance_id=62236
        )

        with self.assertRaises(ValidationError):
            Ecu(
                name="AdpEcu",
                applications=[first_application, second_application],
                diagnostic_trouble_codes=[trouble_code],
            )

    def test_ecu_rejects_duplicate_diagnostic_event_instance_ids(self) -> None:
        trouble_code = DiagnosticTroubleCode(trouble_code=0xED5100)
        first_application, _ = self._application_with_diagnostic_binding(
            trouble_code, name="BrakeApp", event_name="EgoMotionInvalidBrakeApp", event_instance_id=10206
        )
        second_application, _ = self._application_with_diagnostic_binding(
            trouble_code, name="PowertrainApp", event_name="EgoMotionInvalidPowertrainApp", event_instance_id=10206
        )

        with self.assertRaises(ValidationError):
            Ecu(
                name="AdpEcu",
                applications=[first_application, second_application],
                diagnostic_trouble_codes=[trouble_code],
            )

    def test_ecu_accepts_dtc_snapshot_collected_by_application_job(self) -> None:
        job, job_binding = self._diagnostic_job()
        trouble_code = DiagnosticTroubleCode(trouble_code=0x7F9184, snapshots=[job])
        application = Application(
            name="DrivingApp",
            activities=[Activity(name="SpeedLimiter")],
            provided_service_ports=[job_binding.service_port],
            diagnostic_job_bindings=[job_binding],
        )

        ecu = Ecu(
            name="AdpEcu",
            applications=[application],
            diagnostic_trouble_codes=[trouble_code],
            diagnostic_jobs=[job],
        )

        self.assertIs(ecu.diagnostic_trouble_codes[0].snapshots[0], job)
        self.assertEqual(ecu.diagnostic_trouble_codes[0].snapshots[0].service_id, 0x6F07)

    def test_ecu_shares_environmental_job_across_dtcs_and_trigger_applications(self) -> None:
        speed_job, speed_binding = self._diagnostic_job()
        temperature_job, temperature_binding = self._diagnostic_job(job_name="Temperature", service_id=0x5B9C)
        first_trouble_code = DiagnosticTroubleCode(trouble_code=0x7F9184, snapshots=[speed_job, temperature_job])
        second_trouble_code = DiagnosticTroubleCode(trouble_code=0x482E81, snapshots=[speed_job])
        provider_application = Application(
            name="VehicleDataApp",
            activities=[Activity(name="VehicleDataProvider")],
            provided_service_ports=[speed_binding.service_port, temperature_binding.service_port],
            diagnostic_job_bindings=[speed_binding, temperature_binding],
        )
        first_trigger_application, _ = self._application_with_diagnostic_binding(
            first_trouble_code,
            name="BrakeApp",
        )
        second_trigger_application, _ = self._application_with_diagnostic_binding(
            second_trouble_code,
            name="PowertrainApp",
            event_name="PowertrainStateFailure",
            event_instance_id=33765,
        )

        ecu = Ecu(
            name="AdpEcu",
            applications=[provider_application, first_trigger_application, second_trigger_application],
            diagnostic_trouble_codes=[first_trouble_code, second_trouble_code],
            diagnostic_jobs=[speed_job, temperature_job],
        )

        self.assertEqual(ecu.diagnostic_trouble_codes[0].snapshots, [speed_job, temperature_job])
        self.assertIs(ecu.diagnostic_trouble_codes[1].snapshots[0], speed_job)

    def test_ecu_rejects_snapshot_job_not_owned_by_an_application(self) -> None:
        job, _ = self._diagnostic_job()
        trouble_code = DiagnosticTroubleCode(trouble_code=0x7F9184, snapshots=[job])

        with self.assertRaises(ValidationError):
            Ecu(
                name="AdpEcu",
                applications=[self._application()],
                diagnostic_trouble_codes=[trouble_code],
            )

    def test_ecu_requires_each_diagnostic_job_to_be_offered_once(self) -> None:
        job, _ = self._diagnostic_job()

        with self.assertRaises(ValidationError):
            Ecu(name="AdpEcu", applications=[self._application()], diagnostic_jobs=[job])

    def test_ecu_rejects_diagnostic_jobs_with_same_service(self) -> None:
        speed_job, speed_binding = self._diagnostic_job()
        another_speed_job, another_speed_binding = self._diagnostic_job(job_name="VehicleSpeedCopy")
        application = Application(
            name="VehicleDataApp",
            activities=[Activity(name="VehicleDataProvider")],
            provided_service_ports=[speed_binding.service_port, another_speed_binding.service_port],
            diagnostic_job_bindings=[speed_binding, another_speed_binding],
        )

        with self.assertRaises(ValidationError):
            Ecu(name="AdpEcu", applications=[application], diagnostic_jobs=[speed_job, another_speed_job])

    def test_ecu_rejects_diagnostic_job_offered_by_multiple_applications(self) -> None:
        job, job_binding = self._diagnostic_job()
        first_application = Application(
            name="DrivingApp",
            activities=[Activity(name="SpeedLimiter")],
            provided_service_ports=[job_binding.service_port],
            diagnostic_job_bindings=[job_binding],
        )
        second_application = Application(
            name="DiagnosticApp",
            activities=[Activity(name="DiagnosticRunner")],
            provided_service_ports=[job_binding.service_port],
            diagnostic_job_bindings=[job_binding],
        )

        with self.assertRaises(ValidationError):
            Ecu(name="AdpEcu", applications=[first_application, second_application], diagnostic_jobs=[job])


if __name__ == "__main__":
    unittest.main()
