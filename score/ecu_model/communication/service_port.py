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

from score.ecu_model.communication.detail.service_port import _ServicePort
from score.ecu_model.communication.service_interface import InterfaceDefinition
from score.ecu_model.model import ModelElement


class PortSpecification(ModelElement):
    """Binding-independent declaration of a service port."""

    interface_design: InterfaceDefinition = Field(
        ...,
        description="Binding-independent service interface declared by this port",
    )


class ProvidedServicePort(_ServicePort):
    """A service port offered by an application or activity."""


class RequiredServicePort(_ServicePort):
    """A service port consumed by an application or activity."""

    """
    TODO: need to check if port_spec is actually needed, for example to select only specific members uf the used service interface etc.
    """
    port_spec: PortSpecification | None = Field(
        default=None,
        description="Binding-independent design declaration represented by this deployed port",
    )

    @model_validator(mode="after")
    def _validate_interface_matches_port_spec(self) -> "RequiredServicePort":
        if self.port_spec is not None and self.interface.design_element != self.port_spec.interface_design:
            raise ValueError(
                "interface design element must match the interface design declared by the port specification"
            )
        return self
