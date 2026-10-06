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

from pydantic import Field, field_validator, model_validator

from score.ecu_model.architecture.application import Application
from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.ecu_model.diagnostics.dtc import DiagnosticTroubleCode
from score.ecu_model.diagnostics.job import DiagnosticJob
from score.ecu_model.model import ModelElement


class Ecu(ModelElement):
    """A deployment target grouping the applications that run on it."""

    name: Identifier = Field(description="Identifier of the ECU, unique within the owning system")
    namespace: QualifiedName = Field(
        default_factory=QualifiedName,
        description="Namespace in which the ECU is declared",
    )
    applications: list[Application] = Field(
        min_length=1,
        description="Applications deployed on this ECU",
    )
    diagnostic_trouble_codes: list[DiagnosticTroubleCode] = Field(
        default_factory=list,
        description="Diagnostic trouble codes defined for this ECU. Triggering apps use DtcServiceBinding to attach to a specific dem event",
    )
    diagnostic_jobs: list[DiagnosticJob] = Field(
        default_factory=list,
        description="Diagnostic jobs defined for this ECU and offered by applications",
    )
    deployment_properties: dict[str, object] = Field(
        default_factory=dict,
        description="Deployment metadata attached to this ECU",
    )

    @field_validator("deployment_properties")
    @classmethod
    def _validate_property_names(cls, value: dict[str, object]) -> dict[str, object]:
        if any(not key.strip() for key in value):
            raise ValueError("deployment property names must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_unique_application_names(self) -> Ecu:
        application_names = [application.fully_qualified_name for application in self.applications]
        if len(application_names) != len(set(application_names)):
            raise ValueError("application names must be unique within an ECU")
        return self

    @model_validator(mode="after")
    def _validate_diagnostic_trouble_codes(self) -> Ecu:
        trouble_codes = [trouble_code.trouble_code for trouble_code in self.diagnostic_trouble_codes]
        if len(trouble_codes) != len(set(trouble_codes)):
            raise ValueError("diagnostic trouble codes must be unique within an ECU")

        trouble_code_ids = {trouble_code.id for trouble_code in self.diagnostic_trouble_codes}
        diagnostic_job_ids = {job.id for job in self.diagnostic_jobs}
        diagnostic_job_names = [job.name.as_str for job in self.diagnostic_jobs]
        if len(diagnostic_job_names) != len(set(diagnostic_job_names)):
            raise ValueError("diagnostic job names must be unique within an ECU")
        diagnostic_services = [(job.service_type, job.service_id) for job in self.diagnostic_jobs]
        if len(diagnostic_services) != len(set(diagnostic_services)):
            raise ValueError("diagnostic job services must be unique within an ECU")

        if any(
            binding.trouble_code.id not in trouble_code_ids
            for application in self.applications
            for binding in application.diagnostic_bindings
        ):
            raise ValueError("diagnostic bindings must reference a DTC defined by this ECU")

        event_bindings = [binding for application in self.applications for binding in application.diagnostic_bindings]
        event_names = [binding.diagnostic_event_name.as_str for binding in event_bindings]
        if len(event_names) != len(set(event_names)):
            raise ValueError("diagnostic event names must be unique within an ECU")
        event_instance_ids = [binding.diagnostic_event_instance_id for binding in event_bindings]
        if len(event_instance_ids) != len(set(event_instance_ids)):
            raise ValueError("diagnostic event instance ids must be unique within an ECU")

        job_binding_counts = {job_id: 0 for job_id in diagnostic_job_ids}
        for application in self.applications:
            for binding in application.diagnostic_job_bindings:
                if binding.diagnostic_job.id not in diagnostic_job_ids:
                    raise ValueError("diagnostic job bindings must reference a job defined by this ECU")
                job_binding_counts[binding.diagnostic_job.id] += 1
        if any(binding_count != 1 for binding_count in job_binding_counts.values()):
            raise ValueError("each ECU diagnostic job must be offered by exactly one application")

        if any(
            job.id not in diagnostic_job_ids
            for trouble_code in self.diagnostic_trouble_codes
            for job in trouble_code.snapshots
        ):
            raise ValueError("DTC snapshots must reference a diagnostic job defined by this ECU")
        return self

    @property
    def fully_qualified_name(self) -> str:
        """Return the dot-separated ECU name."""
        return QualifiedName((*self.namespace.names, self.name)).as_str
