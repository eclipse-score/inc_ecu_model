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

"""Internal models for FDEPL deployment definitions."""

from __future__ import annotations

from dataclasses import dataclass, field

from score.ecu_model.common.common_name_types import Identifier, QualifiedName
from score.parsers.franca_parser.model.fdepl.specification import (
    DeploymentSpecification,
)


@dataclass
class DeploymentParameter:
    """A deployment-property assignment."""

    name: Identifier
    value: object | None = None


@dataclass
class DeploymentElement:
    """Base deployment of one design-model element."""

    deployed_type: object | None = None
    parameter_set: list[DeploymentParameter] = field(default_factory=list)


@dataclass
class DeploymentDefinition:
    """Base deployment definition with a specification and design target."""

    specification: QualifiedName | DeploymentSpecification | None = None
    target: object | None = None
    name: QualifiedName | None = None
    use_definitions: list[QualifiedName | "DeploymentDefinition"] = field(default_factory=list)
    parameter_set: list[DeploymentParameter] = field(default_factory=list)
    deployment_elements: list[DeploymentElement] = field(default_factory=list)
