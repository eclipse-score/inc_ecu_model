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

"""Internal FDEPL models for type-collection deployment definitions."""

from __future__ import annotations

from dataclasses import dataclass, field

from score.parsers.franca_parser.model.fdepl.definition import (
    DeploymentDefinition,
    DeploymentElement,
    DeploymentParameter,
)
from score.ecu_model.common.common_name_types import QualifiedName
from score.parsers.franca_parser.model.fidl.type_collection import (
    TypeCollection,
)


@dataclass
class TypeOverwrites:
    """Parameter overrides that apply to one or more datatype deployments."""

    deployments: list[DeploymentElement] = field(default_factory=list)
    parameter_set: list[DeploymentParameter] = field(default_factory=list)


@dataclass
class FieldDeployment(DeploymentElement):
    """Deployment properties and type overrides for a struct or union field."""

    type_overwrites: TypeOverwrites | None = None


@dataclass
class StructDeployment(DeploymentElement):
    """Deployment properties for a FIDL struct and its fields."""

    fields: list[FieldDeployment] = field(default_factory=list)


@dataclass
class TypedefDeployment(DeploymentElement):
    """Deployment properties for a FIDL typedef."""


@dataclass
class EnumValueDeployment(DeploymentElement):
    """Deployment properties for one FIDL enumeration value."""


@dataclass
class EnumerationDeployment(DeploymentElement):
    """Deployment properties for a FIDL enumeration and its values."""

    enumerators: list[EnumValueDeployment] = field(default_factory=list)


@dataclass
class ArrayDeployment(DeploymentElement):
    """Deployment properties and type overrides for a FIDL array."""

    type_overwrites: TypeOverwrites | None = None


@dataclass
class UnionDeployment(DeploymentElement):
    """Deployment properties for a FIDL union and its fields."""

    fields: list[FieldDeployment] = field(default_factory=list)


@dataclass
class MapDeployment(DeploymentElement):
    """Deployment properties for a FIDL map and its key and value types."""

    key: list[DeploymentParameter] = field(default_factory=list)
    value: list[DeploymentParameter] = field(default_factory=list)


@dataclass
class StructOverwrites(TypeOverwrites):
    """Type overrides for an inline struct type."""

    fields: list[FieldDeployment] = field(default_factory=list)


@dataclass
class UnionOverwrites(TypeOverwrites):
    """Type overrides for an inline union type."""

    fields: list[FieldDeployment] = field(default_factory=list)


@dataclass
class EnumOverwrites(TypeOverwrites):
    """Type overrides for an inline enumeration type."""

    enumerators: list[EnumValueDeployment] = field(default_factory=list)


TypeCollectionDatatypeDeployment = (
    TypedefDeployment | ArrayDeployment | EnumerationDeployment | StructDeployment | UnionDeployment | MapDeployment
)


@dataclass
class TypeCollectionDeployment(DeploymentDefinition):
    """Deployment definition targeting a FIDL type collection."""

    target: TypeCollection | QualifiedName | None = None
    version_major: int | None = None
    deployment_elements: list[TypeCollectionDatatypeDeployment] = field(default_factory=list)
