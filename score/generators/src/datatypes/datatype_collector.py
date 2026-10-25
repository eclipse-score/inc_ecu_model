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

"""Collect the input datatypes selected for C++ generation."""

from collections.abc import Mapping
from uuid import UUID

from score.ecu_model.model import ModelElement


class DatatypeCollector:
    """Pass the current pickle model's datatype entries to lowering."""

    @staticmethod
    def collect(model: Mapping[str, Mapping[UUID, ModelElement]]) -> tuple[ModelElement, ...]:
        """Collect datatype entries from the loaded model."""
        # TODO: This temporarily follows the current pickle structure.
        # Update extraction and selection once the pickle structure is finalized.
        data_types = model["data_types"]
        return tuple(data_types.values())
