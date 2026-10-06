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
from score.ecu_model.communication.service_interface import InterfaceDefinition, ServiceInterface
from score.ecu_model.communication.service_port import RequiredServicePort
from score.ecu_model.diagnostics.dtc import DiagnosticTroubleCode, DtcServiceBinding
from score.ecu_model.diagnostics.job import DiagnosticJob, DiagnosticServiceType
from score.ecu_model.model import ModelRegistry


class TestDiagnosticTroubleCode(unittest.TestCase):
    def setUp(self) -> None:
        ModelRegistry.elements.clear()

    def _diagnostic_job(
        self,
        job_name: str = "VehicleSpeed",
        service_id: int = 0x6F07,
        service_type: DiagnosticServiceType = DiagnosticServiceType.READ_DATA_BY_IDENTIFIER,
    ) -> DiagnosticJob:
        return DiagnosticJob(
            name=job_name,
            interface=InterfaceDefinition(name=f"{job_name}Interface", version=Version()),
            service_type=service_type,
            service_id=service_id,
        )

    def _required_port(self) -> RequiredServicePort:
        return RequiredServicePort(
            name="VehicleStateConsumer",
            interface=ServiceInterface(
                name="VehicleStateDeployment",
                namespace="deployment",
                design_element=InterfaceDefinition(name="DiagnosticEvent", version=Version()),
            ),
            binding=CommunicationBinding(protocol=ProtocolKind.ARA_COM, network=NetworkKind.SOMEIP),
        )

    def test_dtc_collects_data_identifier_jobs_as_snapshots(self) -> None:
        speed_job = self._diagnostic_job()
        temperature_job = self._diagnostic_job(job_name="Temperature", service_id=0x5B9C)

        trouble_code = DiagnosticTroubleCode(trouble_code=0x7F9184, snapshots=[speed_job, temperature_job])

        self.assertEqual(trouble_code.trouble_code, 0x7F9184)
        self.assertEqual(trouble_code.snapshots, [speed_job, temperature_job])

    def test_dtc_rejects_snapshot_job_that_does_not_read_a_data_identifier(self) -> None:
        routine_job = self._diagnostic_job(job_name="SelfTest", service_type=DiagnosticServiceType.ROUTINE_CONTROL)

        with self.assertRaises(ValidationError):
            DiagnosticTroubleCode(trouble_code=0x7F9184, snapshots=[routine_job])

    def test_dtc_rejects_snapshot_jobs_with_duplicate_data_identifier(self) -> None:
        speed_job = self._diagnostic_job()
        another_speed_job = self._diagnostic_job(job_name="VehicleSpeedCopy")

        with self.assertRaises(ValidationError):
            DiagnosticTroubleCode(trouble_code=0x7F9184, snapshots=[speed_job, another_speed_job])

    def test_dtc_rejects_trouble_code_outside_24_bit_range(self) -> None:
        with self.assertRaises(ValidationError):
            DiagnosticTroubleCode(trouble_code=0x1000000)

    def test_dtc_rejects_trouble_code_given_as_string(self) -> None:
        with self.assertRaises(ValidationError):
            DiagnosticTroubleCode(trouble_code="8360324")

    def test_dtc_service_binding_names_the_event_of_the_triggering_application(self) -> None:
        trouble_code = DiagnosticTroubleCode(trouble_code=0x7F9184)
        required_port = self._required_port()

        binding = DtcServiceBinding(
            trouble_code=trouble_code,
            required_service_port=required_port,
            diagnostic_event_name="VehicleStateFailure",
            diagnostic_event_instance_id=33764,
        )

        self.assertIs(binding.trouble_code, trouble_code)
        self.assertIs(binding.required_service_port, required_port)
        self.assertEqual(binding.diagnostic_event_name.as_str, "VehicleStateFailure")

    def test_dtc_service_binding_rejects_event_instance_id_outside_16_bit_range(self) -> None:
        with self.assertRaises(ValidationError):
            DtcServiceBinding(
                trouble_code=DiagnosticTroubleCode(trouble_code=0x7F9184),
                required_service_port=self._required_port(),
                diagnostic_event_name="VehicleStateFailure",
                diagnostic_event_instance_id=0x10000,
            )


if __name__ == "__main__":
    unittest.main()
