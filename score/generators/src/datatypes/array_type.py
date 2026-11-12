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

"""Build fixed/dynamic array aliases and anonymous array usage expressions."""

from collections.abc import Mapping

from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.enum import EnumDataType
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.data_types.union import UnionDataType
from score.generators.src.common.common_utils import generate_header_file_guard
from score.generators.src.datatypes.cpp_model import CppAlias, CppHeaderModel
from score.generators.src.datatypes.cpp_type_registry import CppTypeInfo, CppTypeRegistry
from score.generators.src.datatypes.primitive_type import register_primitive


def get_array_type_info(
    datatype: ArrayDataType,
    registry: CppTypeRegistry,
    deployment_properties: Mapping[str, object] | None = None,
    context: str | None = None,
) -> CppTypeInfo:
    """Return C++ type information for a named or inline array."""
    if datatype.is_inline:
        if deployment_properties is None:
            raise NotImplementedError("Inline arrays require field deployment context")
        return _build_array_expression(datatype, registry, deployment_properties, context or "<inline array>")
    return registry.named_types[datatype.fully_qualified_name]


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


def _effective_bounds(datatype: ArrayDataType, properties: Mapping[str, object], context: str) -> tuple[int, int]:
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


def _build_array_expression(
    datatype: ArrayDataType,
    registry: CppTypeRegistry,
    deployment_properties: Mapping[str, object],
    context: str,
) -> CppTypeInfo:
    """Resolve bounds using the explicitly supplied deployment scope.

    Equal positive bounds select std::array; all others select std::vector,
    including (0, 0), without runtime bound enforcement.
    """
    minimum, maximum = _effective_bounds(datatype, deployment_properties, context)
    element = datatype.data_type
    if isinstance(element, PrimitiveDataType):
        element_info = register_primitive(element, registry)
    elif isinstance(element, ArrayDataType):
        element_info = get_array_type_info(element, registry)
    elif isinstance(element, (EnumDataType, StructDataType, TypedefDataType, UnionDataType)):
        element_info = registry.named_types[element.fully_qualified_name]
    else:
        raise NotImplementedError(f"Unsupported array element type: {element}")
    is_fixed = minimum == maximum and maximum > 0
    container = "array" if is_fixed else "vector"
    size_argument = f", {maximum}" if is_fixed else ""
    return CppTypeInfo(
        source_type_name="",
        cpp_type_name=f"std::{container}<{element_info.cpp_type_name}{size_argument}>",
        required_includes=tuple(sorted({f"<{container}>", *element_info.required_includes})),
    )


def build_array_header(datatype: ArrayDataType, registry: CppTypeRegistry) -> CppHeaderModel:
    """Register a named array alias after its element dependencies complete."""
    if datatype.is_inline or datatype.name is None:
        raise ValueError("Only named arrays have independent headers")
    expression = _build_array_expression(
        datatype, registry, datatype.deployment_properties, datatype.fully_qualified_name
    )
    name = datatype.name.as_str
    namespaces = tuple(segment.as_str for segment in datatype.namespace)
    type_info = registry.register_named_type(datatype.fully_qualified_name, name, namespaces)
    path = type_info.required_includes[0]
    header = CppHeaderModel(
        path=path,
        guard=generate_header_file_guard(path),
        namespaces=namespaces,
        includes=expression.required_includes,
        declaration=CppAlias(name, expression.cpp_type_name),
    )
    type_info.header_model = header
    return header
