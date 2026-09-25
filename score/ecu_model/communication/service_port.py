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

from score.ecu_model.communication.detail.service_port import _ServicePort


class ProvidedServicePort(_ServicePort):
    """A service port offered by an application or activity."""


class RequiredServicePort(_ServicePort):
    """A service port consumed by an application or activity."""
