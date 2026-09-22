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

from score.ecu_model.data_types.common import DataTypeOrReference
from score.ecu_model.data_types.identifier import Identifier
from score.ecu_model.model import ModelElement


class MessageChannel(ModelElement):
    """Represents a communication channel for message-oriented ports."""

    name: Identifier = Field(description="Identifier of the message channel")
    data_type: DataTypeOrReference = Field(
        description="Payload data type carried by this channel",
    )
    channel_id: int | None = Field(
        default=None,
        ge=0,
        strict=True,
        description="Optional unique identifier for the message channel from the deployment",
    )
