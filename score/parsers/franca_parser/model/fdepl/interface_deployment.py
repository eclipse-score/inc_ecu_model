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

"""Parser context for resolving FDEPL interface deployment declarations."""

from __future__ import annotations

from dataclasses import dataclass, field

from score.ecu_model.common.version import Version
from score.ecu_model.communication.service_interface import InterfaceDefinition
from score.ecu_model.data_types.identifier import Identifier
from score.parsers.franca_parser.model.fdepl.definition import (
    DeploymentDefinition,
    DeploymentElement,
    DeploymentParameter,
)


@dataclass
class ArgumentDeployment(DeploymentElement):
    """Deployment properties for one argument."""


@dataclass
class EventGroup(DeploymentElement):
    """One event group declared by an effective service interface."""

    name: Identifier | None = None


@dataclass
class EventGroupReference:
    """Event-group assignments for an attribute or broadcast."""

    used_event_groups: list[EventGroup] = field(default_factory=list)
    parameter_set: list[DeploymentParameter] = field(default_factory=list)


@dataclass
class AttributeDeployment(DeploymentElement):
    """All deployment data attached to one interface attribute."""

    event_groups: EventGroupReference | None = None


@dataclass
class MethodDeployment(DeploymentElement):
    """All deployment data attached to one interface method."""

    inputs: dict[Identifier, ArgumentDeployment] = field(default_factory=dict)
    outputs: dict[Identifier, ArgumentDeployment] = field(default_factory=dict)


@dataclass
class BroadcastDeployment(DeploymentElement):
    """All deployment data attached to one interface broadcast."""

    outputs: dict[Identifier, ArgumentDeployment] = field(default_factory=dict)
    event_groups: EventGroupReference | None = None


@dataclass
class InterfaceDeployment(DeploymentDefinition):
    """Deployment definition targeting a FIDL interface."""

    target: InterfaceDefinition = field(kw_only=True)
    version: Version | None = None
