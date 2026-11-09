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

"""Resolve effective array dimension bounds from model and deployment data."""

from collections.abc import Mapping

from score.ecu_model.data_types.array import ArrayDataType


def _deployment_bound(properties: Mapping[str, object], suffix: str, context: str) -> int | None:
    """Require SOME/IP, IPC and Persistency agreement; use Diagnostic only as fallback."""
    values = {prefix: properties.get(prefix + "Array" + suffix) for prefix in ("SomeIp", "Ipc", "Persistency")}
    for value in values.values():
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValueError(f"Invalid array {suffix} for {context}: expected integer, got {value!r}")
    if len({value for value in values.values() if value is not None}) > 1:
        raise ValueError(f"Conflicting array {suffix} for {context}: {values}")
    selected = next((value for value in values.values() if value is not None), None)
    if selected is not None:
        return selected
    diagnostic = properties.get("DiagnosticArray" + suffix)
    if diagnostic is not None and (not isinstance(diagnostic, int) or isinstance(diagnostic, bool)):
        raise ValueError(f"Invalid array {suffix} for {context}: expected integer, got {diagnostic!r}")
    return diagnostic


def effective_bounds(datatype: ArrayDataType, properties: Mapping[str, object], context: str) -> tuple[int, int]:
    """Prefer explicit max; otherwise resolve both bounds from deployment without mutation."""
    maximum = datatype.dimension_max
    if maximum is not None:
        minimum = datatype.dimension_min if datatype.dimension_min is not None else maximum
    else:
        minimum = _deployment_bound(properties, "MinLength", context)
        maximum = _deployment_bound(properties, "MaxLength", context)
    missing = [name for name, value in (("min", minimum), ("max", maximum)) if value is None]
    if missing:
        raise ValueError(f"Missing array bounds for {context}: {', '.join(missing)}")
    if (
        not isinstance(minimum, int)
        or isinstance(minimum, bool)
        or not isinstance(maximum, int)
        or isinstance(maximum, bool)
        or minimum < 0
        or maximum < minimum
    ):
        raise ValueError(f"Invalid array bounds for {context}: ({minimum}, {maximum}); expected 0 <= min <= max")
    return minimum, maximum
