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

from pydantic import Field

from score.ecu_model.common.asil_level import AsilLevel
from score.ecu_model.common.version import Version
from score.ecu_model.communication.message_port import ProvidedMessagePort, RequiredMessagePort
from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.ecu_model.model import RegisteredModelElement


class Activity(RegisteredModelElement):
    """Executable unit in regards to scheduling with typed input and output ports."""

    name: Identifier = Field(description="Identifier of the activity, unique within the owning application")
    namespace: QualifiedName = Field(
        default_factory=QualifiedName,
        description="Namespace in which the activity is declared",
    )
    asil: AsilLevel = Field(default=AsilLevel.QM, description="ISO 26262 ASIL level")
    version: Version = Field(default_factory=Version, description="Semantic version of the activity")
    inputs: list[RequiredMessagePort] = Field(
        default_factory=list,
        description="All input ports consumed by this activity",
    )
    outputs: list[ProvidedMessagePort] = Field(
        default_factory=list,
        description="All output ports published by this activity",
    )

    @property
    def fully_qualified_name(self) -> str:
        """Return the dot-separated activity name."""
        return QualifiedName((*self.namespace.names, self.name)).as_str
