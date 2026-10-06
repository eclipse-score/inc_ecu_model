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

from pydantic import Field, model_validator

from score.ecu_model.communication.service_port import RequiredServicePort
from score.ecu_model.data_types.identifier import Identifier
from score.ecu_model.diagnostics.job import DiagnosticJob, DiagnosticServiceType
from score.ecu_model.model import ModelElement

# Services whose service_id is a data identifier that can be stored in a DTC snapshot.
_SNAPSHOT_SERVICE_TYPES = frozenset(
    {DiagnosticServiceType.READ_DATA_BY_IDENTIFIER, DiagnosticServiceType.READ_WRITE_DATA_BY_IDENTIFIER}
)


class DiagnosticTroubleCode(ModelElement):
    """Diagnostic trouble code declared for an ECU, with its environmental-data snapshots."""

    trouble_code: int = Field(
        ge=0,
        le=0xFFFFFF,
        strict=True,
        description="24-bit DTC number, conventionally written in hex, e.g. 0x7F9184",
    )
    snapshots: list[DiagnosticJob] = Field(
        default_factory=list,
        description="Data identifier jobs whose data is stored as environmental data with this DTC",
    )
    deployment_properties: dict[str, object] = Field(
        default_factory=dict,
        description="Deployment metadata attached to this DTC",
    )

    @model_validator(mode="after")
    def _validate_snapshots(self) -> DiagnosticTroubleCode:
        if any(job.service_type not in _SNAPSHOT_SERVICE_TYPES for job in self.snapshots):
            raise ValueError("DTC snapshots must reference jobs that read a data identifier")
        data_identifiers = [job.service_id for job in self.snapshots]
        if len(data_identifiers) != len(set(data_identifiers)):
            raise ValueError("DTC snapshots must not contain duplicate data identifiers")
        return self


class DtcServiceBinding(ModelElement):
    """Association between an ECU DTC and an application's required service port."""

    trouble_code: DiagnosticTroubleCode
    required_service_port: RequiredServicePort
    diagnostic_event_name: Identifier = Field(
        description="""Name of the diagnostic event associated with this DTC service binding,
provider specific since multiple producers may trigger the same event/dtc.""",
    )
    diagnostic_event_instance_id: int = Field(
        ge=0,
        le=0xFFFF,
        strict=True,
        description="Numeric identifier of the diagnostic event, unique within the ECU",
    )
