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

from score.ecu_model.communication.detail.base_port import _BasePort
from score.ecu_model.communication.message_channel import MessageChannel


class _MessagePort(_BasePort):
    """Shared attributes for message-oriented communication ports."""

    channel: MessageChannel = Field(..., description="The message channel associated with this port")

    debug_only: bool = Field(
        default=False,
        description="Whether this port is a debug-only interface rather than production data",
    )

    # asil: AsilLevel = Field(default=AsilLevel.QM, description="Data integrity level promised by the sender")
    # binding: Binding = Field(..., description="Communication binding / deployment for this port")
    def model_post_init(self, context: object, /) -> None:
        """Reject direct instantiation of the abstract base port."""
        if type(self) is _MessagePort:
            raise TypeError("_MessagePort is abstract, instantiate a concrete port")
        super().model_post_init(context)
