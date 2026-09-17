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

from pydantic import BaseModel, Field, field_validator, model_validator

from score.ecu_model.common.version import Version
from score.ecu_model.communication.service_interface.detail import _DeploymentBinding
from score.ecu_model.data_types.common import DataTypeReference
from score.ecu_model.data_types.composite import DataTypeField
from score.ecu_model.data_types.enum import EnumDataType
from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.ecu_model.model import ModelElement


class Broadcast(BaseModel):
    """Named service broadcast carrying zero or more output data types."""

    name: Identifier
    outputs: list[DataTypeField] = Field(default_factory=list)


class Attribute(BaseModel):
    """Named service attribute with Franca access qualifiers."""

    name: Identifier
    data_type: DataTypeReference
    access_q_readonly: bool = False
    access_q_noread: bool = False
    access_q_nosubscriptions: bool = False


class Method(BaseModel):
    """Named service method with input, output, and error definitions."""

    name: Identifier
    inputs: list[DataTypeField] = Field(default_factory=list)
    outputs: list[DataTypeField] = Field(default_factory=list)
    errors: EnumDataType | None = None
    error_enum: DataTypeReference | None = None
    fire_and_forget: bool = False

    @model_validator(mode="after")
    def _validate_single_error_definition(self) -> "Method":
        if self.errors is not None and self.error_enum is not None:
            raise ValueError("method must define either errors or error_enum, not both")
        return self


class BroadcastBinding(_DeploymentBinding):
    """Deployment metadata attached to a service broadcast."""


class AttributeBinding(_DeploymentBinding):
    """Deployment metadata attached to a service attribute."""


class MethodBinding(_DeploymentBinding):
    """Deployment metadata attached to a service method."""


class InterfaceDesign(ModelElement):
    """Reusable design-time declaration of an interface."""

    name: Identifier
    namespace: QualifiedName = Field(default_factory=QualifiedName)
    version: Version
    broadcasts: dict[Identifier, Broadcast] = Field(default_factory=dict)
    attributes: dict[Identifier, Attribute] = Field(default_factory=dict)
    methods: dict[Identifier, Method] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_namespace(cls, data: object) -> object:
        if isinstance(data, dict) and isinstance(data.get("namespace"), str):
            data = dict(data)
            data["namespace"] = QualifiedName(tuple(Identifier(part) for part in data["namespace"].split(".")))
        return data

    @model_validator(mode="after")
    def _validate_member_keys(self) -> "InterfaceDesign":
        for members, kind in (
            (self.broadcasts, "broadcast"),
            (self.attributes, "attribute"),
            (self.methods, "method"),
        ):
            if any(str(key) != str(member.name) for key, member in members.items()):
                raise ValueError(f"interface {kind} keys must match declared {kind} names")
        return self

    @property
    def fully_qualified_name(self) -> str:
        """Return the dot-separated Franca interface name."""
        return QualifiedName((*self.namespace.names, self.name)).as_str


class Interface(ModelElement):
    """Deployment metadata for an interface design."""

    name: Identifier
    namespace: QualifiedName = Field(default_factory=QualifiedName)
    design_element: InterfaceDesign
    service_id: int | None = Field(default=None, ge=0, strict=True)
    deployment_properties: dict[str, object] = Field(default_factory=dict)
    broadcast_bindings: dict[Identifier, BroadcastBinding] = Field(default_factory=dict)
    attribute_bindings: dict[Identifier, AttributeBinding] = Field(default_factory=dict)
    method_bindings: dict[Identifier, MethodBinding] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_namespace(cls, data: object) -> object:
        if isinstance(data, dict) and isinstance(data.get("namespace"), str):
            data = dict(data)
            data["namespace"] = QualifiedName(tuple(Identifier(part) for part in data["namespace"].split(".")))
        return data

    @field_validator("deployment_properties")
    @classmethod
    def _validate_property_names(cls, value: dict[str, object]) -> dict[str, object]:
        if any(not key.strip() for key in value):
            raise ValueError("deployment property names must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_member_bindings(self) -> "Interface":
        for bindings, members, kind in (
            (self.broadcast_bindings, self.design_element.broadcasts, "broadcast"),
            (self.attribute_bindings, self.design_element.attributes, "attribute"),
            (self.method_bindings, self.design_element.methods, "method"),
        ):
            if any(name not in members for name in bindings):
                raise ValueError(f"interface {kind} bindings must reference declared {kind}s")
        return self
