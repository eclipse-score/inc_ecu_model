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

from score.ecu_model.architecture.activity import Activity
from score.ecu_model.communication.service_port import ProvidedServicePort, RequiredServicePort
from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.ecu_model.diagnostics.dtc import DtcServiceBinding
from score.ecu_model.diagnostics.job import DiagnosticJobBinding
from score.ecu_model.model import ModelElement


class Application(ModelElement):
    """A process grouping one or more activities."""

    name: Identifier = Field(description="Identifier of the application, unique within the owning ECU")
    namespace: QualifiedName = Field(
        default_factory=QualifiedName,
        description="Namespace in which the application is declared",
    )
    activities: list[Activity] = Field(
        min_length=1,
        description="Activities contained in this application",
    )
    provided_service_ports: list[ProvidedServicePort] = Field(
        default_factory=list,
        description="Service ports provided by this application",
    )
    required_service_ports: list[RequiredServicePort] = Field(
        default_factory=list,
        description="Service ports required by this application",
    )
    diagnostic_job_bindings: list[DiagnosticJobBinding] = Field(
        default_factory=list,
        description="ECU diagnostic jobs offered through this application's service ports",
    )
    diagnostic_bindings: list[DtcServiceBinding] = Field(
        default_factory=list,
        description="Associations between ECU DTCs and required service ports of this application",
    )
    deployment_properties: dict[str, object] = Field(
        default_factory=dict,
        description="Deployment metadata attached to this application",
    )

    @field_validator("deployment_properties")
    @classmethod
    def _validate_property_names(cls, value: dict[str, object]) -> dict[str, object]:
        if any(not key.strip() for key in value):
            raise ValueError("deployment property names must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_unique_activity_names(self) -> Application:
        activity_names = [activity.fully_qualified_name for activity in self.activities]
        if len(activity_names) != len(set(activity_names)):
            raise ValueError("activity names must be unique within an application")
        return self

    @model_validator(mode="after")
    def _validate_diagnostic_references(self) -> Application:
        job_ids = [binding.diagnostic_job.id for binding in self.diagnostic_job_bindings]
        if len(job_ids) != len(set(job_ids)):
            raise ValueError("an application must bind each diagnostic job at most once")

        required_port_ids = {port.id for port in self.required_service_ports}
        provided_port_ids = {port.id for port in self.provided_service_ports}
        binding_keys = [
            (binding.trouble_code.id, binding.required_service_port.id, binding.diagnostic_event_name)
            for binding in self.diagnostic_bindings
        ]
        if len(binding_keys) != len(set(binding_keys)):
            raise ValueError("diagnostic bindings must be unique within an application")
        if any(binding.required_service_port.id not in required_port_ids for binding in self.diagnostic_bindings):
            raise ValueError("diagnostic bindings must reference an application's required service port")
        if any(binding.service_port.id not in provided_port_ids for binding in self.diagnostic_job_bindings):
            raise ValueError("diagnostic job bindings must reference an application's provided service port")
        return self

    @property
    def fully_qualified_name(self) -> str:
        """Return the dot-separated application name."""
        return QualifiedName((*self.namespace.names, self.name)).as_str
