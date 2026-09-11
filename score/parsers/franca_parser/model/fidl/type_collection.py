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

"""FIDL type collection parser model."""

from dataclasses import dataclass, field

from score.ecu_model.common.common_name_types import Identifier


@dataclass
class TypeCollection:
    """FIDL type collection and the datatypes it declares."""

    name: Identifier | None
    datatypes: list[object] = field(default_factory=list)
