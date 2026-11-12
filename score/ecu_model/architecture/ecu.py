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

from uuid import UUID

from pydantic import Field, field_validator, model_validator

from score.ecu_model.architecture.application import Application
from score.ecu_model.architecture.chain import Chain
from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.ecu_model.model import RegisteredModelElement


class Ecu(RegisteredModelElement):
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
    chains: list[Chain] = Field(
        default_factory=list,
        description="Scheduling chains spanning the applications of this ECU",
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
    def _validate_chains(self) -> Ecu:
        chain_names = [chain.fully_qualified_name for chain in self.chains]
        if len(chain_names) != len(set(chain_names)):
            raise ValueError("chain names must be unique within an ECU")

        deployed_applications = {application.id for application in self.applications}
        chain_by_application: dict[UUID, Chain] = {}
        for chain in self.chains:
            for application in chain.applications:
                if application.id not in deployed_applications:
                    raise ValueError(
                        f"chain '{chain.fully_qualified_name}' references application "
                        f"'{application.fully_qualified_name}' which is not deployed on this ECU"
                    )
                owning_chain = chain_by_application.setdefault(application.id, chain)
                if owning_chain is not chain:
                    raise ValueError(
                        f"application '{application.fully_qualified_name}' is part of multiple chains: "
                        f"'{owning_chain.fully_qualified_name}' and '{chain.fully_qualified_name}'"
                    )
        return self

    @property
    def fully_qualified_name(self) -> str:
        """Return the dot-separated ECU name."""
        return QualifiedName((*self.namespace.names, self.name)).as_str
