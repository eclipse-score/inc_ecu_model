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

from typing import Any
from score.ecu_model.communication.protocol import ProtocolKind

from pydantic import Field, model_validator

from score.ecu_model.common.asil_level import AsilLevel
from score.ecu_model.common.version import Version
from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.ecu_model.model import ModelElement


class _BasePort(ModelElement):
    """Shared metadata for activity and service communication ports."""

    name: Identifier = Field(description="Port identifier, unique within the owning activity")
    namespace: QualifiedName = Field(
        default_factory=lambda: QualifiedName((Identifier("adp"),)),
        description="Namespace in which the port is declared",
    )
    version: Version = Field(
        default_factory=lambda: Version(major=1, minor=0, patch=0),
        description="Semantic version of the port interface",
    )
    deployment_properties: dict[str, object] = Field(default_factory=dict)
    debug_only: bool = Field(
        default=False,
        description="Whether this port is a debug-only interface rather than production data",
    )
    asil: AsilLevel = Field(
        default=AsilLevel.QM,
        description="Data integrity level promised by the sender (ISO 26262)",
    )
    protocol: ProtocolKind | None = Field(
        description="Communication protocol used by this port",
    )

    def model_post_init(self, context: Any, /) -> None:
        """Reject direct instantiation of the abstract base port."""
        if type(self) is _BasePort:
            raise TypeError("_BasePort is abstract, instantiate a concrete port")
        super().model_post_init(context)

    @model_validator(mode="before")
    @classmethod
    def _coerce_namespace(cls, data: object) -> object:
        if isinstance(data, dict) and isinstance(data.get("namespace"), str):
            data = dict(data)
            data["namespace"] = QualifiedName(tuple(Identifier(part) for part in data["namespace"].split(".")))
        return data
