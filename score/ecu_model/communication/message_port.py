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

from score.ecu_model.communication.detail.message_port import _MessagePort


class ProvidedMessagePort(_MessagePort):
    """A message port offered by an application or activity."""

    max_published_messages: int = Field(
        default=1,
        gt=0,
        strict=True,
        description="Max output queue size",
    )


class RequiredMessagePort(_MessagePort):
    """A message port consumed by an application or activity."""

    max_required_messages: int = Field(
        default=1,
        gt=0,
        strict=True,
        description="Max input queue size, window size regarding all messages published by the producer",
    )
