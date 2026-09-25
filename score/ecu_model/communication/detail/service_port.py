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

from score.ecu_model.communication.detail.base_port import _BasePort
from score.ecu_model.communication.message_channel import ModelElement
from score.ecu_model.communication.service_interface import ServiceInterface, InterfaceDefinition


class PortDefinition(ModelElement):
    """Binding-independent declaration of a service port."""

    interface_design: InterfaceDefinition = Field(
        ...,
        description="Binding-independent service interface declared by this port",
    )


class _ServicePort(_BasePort):
    """Communication port that provides or requires a service interface."""

    interface: ServiceInterface
    instance_id: int | None = Field(
        default=None,
        gt=0,
        strict=True,
        description="Optional positive service instance identifier from the source deployment",
    )

    """
    TODO: need to check if design_element is actually needed, for example to select only specific members uf the used service interface etc.
    """
    design_element: PortDefinition | None = Field(
        default=None,
        description="Binding-independent design declaration represented by this deployed port",
    )

    @model_validator(mode="after")
    def _validate_interface_matches_port_spec(self) -> "_BasePort":
        if self.design_element is not None and self.interface.design_element != self.design_element.interface_design:
            raise ValueError(
                "interface design element must match the interface design declared by the port specification"
            )
        return self

    @field_validator("deployment_properties")
    @classmethod
    def _validate_property_names(cls, value: dict[str, object]) -> dict[str, object]:
        if any(not key.strip() for key in value):
            raise ValueError("deployment property names must not be empty")
        return value

    def model_post_init(self, context: object, /) -> None:
        """Reject direct instantiation of the abstract base port."""
        if type(self) is _ServicePort:
            raise TypeError("_ServicePort is abstract, instantiate a concrete port")
        super().model_post_init(context)
