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

"""Select concrete service deployments from the loaded ECU model."""

from collections.abc import Mapping
from uuid import UUID

from score.ecu_model.communication.service_interface import ServiceInterface
from score.ecu_model.model import ModelElement


class LayoutCollector:
    """Select layout inputs from the model's service-interface section."""

    @staticmethod
    def collect(model: Mapping[str, Mapping[UUID, ModelElement]]) -> tuple[ServiceInterface, ...]:
        """Select deployments when the model has a service-interface section."""
        service_interfaces = model.get("service_interfaces", {})
        return tuple(element for element in service_interfaces.values() if isinstance(element, ServiceInterface))
