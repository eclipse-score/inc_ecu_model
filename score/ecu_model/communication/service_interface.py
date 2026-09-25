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
from score.ecu_model.data_types.common import DataTypeOrReference, DataTypeReference
from score.ecu_model.data_types.composite import DataTypeField
from score.ecu_model.data_types.enum import EnumDataType
from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.ecu_model.model import ModelElement


class Broadcast(BaseModel):
    """Named service broadcast / event carrying zero or more output data types."""

    name: Identifier
    outputs: list[DataTypeField] = Field(default_factory=list)


class Attribute(BaseModel):
    """Named service attribute field with access properties."""

    name: Identifier
    data_type: DataTypeOrReference = Field(..., description="Specifies the data type of the attribute")
    has_getter: bool = Field(default=True, description="Indicates if the attribute has a getter method")
    has_setter: bool = Field(default=True, description="Indicates if the attribute has a setter method")
    subscribable: bool = Field(default=True, description="Indicates if the attribute can be subscribed to")


class Method(BaseModel):
    """Named service method with input, output, and error definitions."""

    name: Identifier
    inputs: list[DataTypeField] = Field(
        default_factory=list, description="Specifies the input data types of the method"
    )
    outputs: list[DataTypeField] = Field(
        default_factory=list, description="Specifies the output data types of the method"
    )
    error_return_codes: EnumDataType | DataTypeReference | None = Field(
        default=None, description="Specifies the error return codes of the method"
    )
    fire_and_forget: bool = Field(
        default=False, description="Indicates if the method requires acknowledgment on bus level"
    )


class InterfaceDefinition(ModelElement):
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
        """
        Allow for specifying the namespace as a simple dot-separated string instead of a QualifiedName object during construction.
        """
        if isinstance(data, dict) and isinstance(data.get("namespace"), str):
            data = dict(data)
            data["namespace"] = QualifiedName(tuple(Identifier(part) for part in data["namespace"].split(".")))
        return data

    @model_validator(mode="after")
    def _validate_member_keys(self) -> "InterfaceDefinition":
        """Validate that the keys of all member dictionaries match the declared member names."""
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
        """Return the dot-separated interface name."""
        return QualifiedName((*self.namespace.names, self.name)).as_str


class ServiceInterface(ModelElement):
    """Concrete deployment of an InterfaceDefinition."""

    name: Identifier
    namespace: QualifiedName = Field(default_factory=QualifiedName)
    design_element: InterfaceDefinition
    service_id: int | None = Field(default=None, ge=0, strict=True)
    deployment_properties: dict[str, object] = Field(default_factory=dict)
    interface_deployment_properties: dict[str, object] = Field(default_factory=dict)
    broadcast_deployment_properties: dict[Identifier, dict[str, object]] = Field(default_factory=dict)
    attribute_deployment_properties: dict[Identifier, dict[str, object]] = Field(default_factory=dict)
    method_deployment_properties: dict[Identifier, dict[str, object]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_namespace(cls, data: object) -> object:
        """
        Allow for specifying the namespace as a simple dot-separated string instead of a QualifiedName object during construction.
        """
        if isinstance(data, dict) and isinstance(data.get("namespace"), str):
            data = dict(data)
            data["namespace"] = QualifiedName(tuple(Identifier(part) for part in data["namespace"].split(".")))
        return data

    @field_validator(
        "deployment_properties",
        "interface_deployment_properties",
        "broadcast_deployment_properties",
        "attribute_deployment_properties",
        "method_deployment_properties",
    )
    @classmethod
    def _validate_property_names(
        cls, value: dict[str, object] | dict[Identifier, dict[str, object]]
    ) -> dict[str, object] | dict[Identifier, dict[str, object]]:
        if isinstance(value, dict):
            for member_properties in value.values():
                if isinstance(member_properties, dict) and any(not key.strip() for key in member_properties):
                    raise ValueError("deployment property names must not be empty")
            if any(not key.strip() for key in value if isinstance(key, str)):
                raise ValueError("deployment property names must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_member_deployment_properties(self) -> "ServiceInterface":
        """
        Validate that all member-specific deployment data references declared members in the interface design element
        and all declared members are covered by deployment data.
        """
        for member_properties, members, kind in (
            (self.broadcast_deployment_properties, self.design_element.broadcasts, "broadcast"),
            (self.attribute_deployment_properties, self.design_element.attributes, "attribute"),
            (self.method_deployment_properties, self.design_element.methods, "method"),
        ):
            keys = {str(name) for name in member_properties}
            names = {str(name) for name in members}
            if any(name not in names for name in keys):
                raise ValueError(f"interface {kind} deployment properties must reference declared {kind}s")
            if any(name not in keys for name in names):
                raise ValueError(f"interface {kind} members must be covered by deployment properties")
        return self
