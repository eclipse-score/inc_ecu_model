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
from score.ecu_model.model import RegisteredModelElement


class Application(RegisteredModelElement):
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

    @property
    def fully_qualified_name(self) -> str:
        """Return the dot-separated application name."""
        return QualifiedName((*self.namespace.names, self.name)).as_str
