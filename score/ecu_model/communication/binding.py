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

from enum import Enum

from pydantic import ConfigDict, Field

from score.ecu_model.model import RegisteredModelElement


class ProtocolKind(str, Enum):
    """Discriminator values for concrete communication binding models."""

    ARA_COM = "ARA::COM"
    ARA_DIAG = "ARA::DIAG"
    MW_COM = "MW::COM"
    MW_DIAG = "MW::DIAG"


class NetworkKind(str, Enum):
    """Discriminator values for binding specific bus protocols"""

    SOMEIP = "SOMEIP"
    IPC = "IPC"


class CommunicationBinding(RegisteredModelElement):
    """Generic core communication binding for all supported platform protocols."""

    model_config = ConfigDict(validate_assignment=True)
    protocol: ProtocolKind = Field(..., description="Transport protocol identifier")
    network: NetworkKind = Field(
        description="Optional underlying network transport, e.g. SOMEIP, IPC, or IPC_ASIL_B",
    )
