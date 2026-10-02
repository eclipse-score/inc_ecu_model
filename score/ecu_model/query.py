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

"""Queries over the ECU model registry."""

from collections.abc import Iterable

from score.ecu_model.data_types.common import DataTypeBase
from score.ecu_model.model import ModelElement, ModelRegistry


def datatypes_by_name(elements: Iterable[ModelElement] | None = None) -> dict[str, DataTypeBase]:
    """Index named datatypes from the registry (or supplied elements) by fully qualified name.

    Raises:
        ValueError: If multiple datatypes have the same fully qualified name.
    """
    datatypes: dict[str, DataTypeBase] = {}
    for element in ModelRegistry.elements.values() if elements is None else elements:
        if not isinstance(element, DataTypeBase) or element.name is None:
            continue
        name = element.fully_qualified_name
        if name in datatypes:
            raise ValueError(f"Duplicate datatype name: {name}")
        datatypes[name] = element
    return datatypes
