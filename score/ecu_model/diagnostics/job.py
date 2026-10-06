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

from __future__ import annotations

from enum import Enum

from pydantic import Field, field_validator, model_validator

from score.ecu_model.communication.service_interface import InterfaceDefinition
from score.ecu_model.communication.service_port import ProvidedServicePort
from score.ecu_model.data_types.identifier import Identifier
from score.ecu_model.model import ModelElement


class DiagnosticServiceType(str, Enum):
    """UDS service implemented by a diagnostic job."""

    CLEAR_DIAGNOSTIC_INFORMATION = "ClearDiagnosticInformation"
    COMMUNICATION_CONTROL = "CommunicationControl"
    CONTROL_DTC_SETTING = "ControlDTCSetting"
    DIAGNOSTIC_SESSION_CONTROL = "DiagnosticSessionControl"
    ECU_RESET = "EcuReset"
    READ_DATA_BY_IDENTIFIER = "ReadDataByIdentifier"
    READ_DTC_INFORMATION = "ReadDTCinformation"
    READ_WRITE_DATA_BY_IDENTIFIER = "ReadWriteDataByIdentifier"
    REQUEST_DOWNLOAD = "RequestDownload"
    REQUEST_FILE_TRANSFER = "RequestFileTransfer"
    REQUEST_TRANSFER_EXIT = "RequestTransferExit"
    REQUEST_UPLOAD = "RequestUpload"
    RESPONSE_ON_EVENT = "ResponseOnEvent"
    ROUTINE_CONTROL = "RoutineControl"
    TESTER_PRESENT = "TesterPresent"
    TRANSFER_DATA = "TransferData"
    WRITE_DATA_BY_IDENTIFIER = "WriteDataByIdentifier"


class DiagnosticJob(ModelElement):
    """ECU-owned diagnostic job, implemented by one service interface."""

    name: Identifier
    interface: InterfaceDefinition = Field(description="Service interface whose methods implement this job")
    service_type: DiagnosticServiceType
    service_id: int = Field(
        ge=0,
        le=0xFFFF,
        strict=True,
        description="UDS identifier of the job, e.g. the data identifier of a ReadDataByIdentifier job",
    )
    deployment_properties: dict[str, object] = Field(
        default_factory=dict,
        description="Deployment metadata attached to this job, e.g. sessions and security access",
    )

    @field_validator("deployment_properties")
    @classmethod
    def _validate_property_names(cls, value: dict[str, object]) -> dict[str, object]:
        if any(not key.strip() for key in value):
            raise ValueError("deployment property names must not be empty")
        return value


class DiagnosticJobBinding(ModelElement):
    """Bind an ECU diagnostic job to the service port through which an application offers it."""

    diagnostic_job: DiagnosticJob
    service_port: ProvidedServicePort

    @model_validator(mode="after")
    def _validate_interface(self) -> DiagnosticJobBinding:
        if self.service_port.interface.design_element != self.diagnostic_job.interface:
            raise ValueError("service port must provide the interface of the diagnostic job")
        return self
