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

from pydantic import Field, field_validator

from score.ecu_model.communication.detail.base_port import _BasePort
from score.ecu_model.communication.service_interface import ServiceInterface


class _ServicePort(_BasePort):
    """Communication port that provides or requires a service interface."""

    interface: ServiceInterface
    # design_element: PortDesign | None = Field(
    #     default=None,
    #     description="Binding-independent design declaration represented by this deployed port",
    # )
    instance_id: int | None = Field(
        default=None,
        gt=0,
        strict=True,
        description="Optional positive service instance identifier from the source deployment",
    )
    deployment_properties: dict[str, object] = Field(default_factory=dict)

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
