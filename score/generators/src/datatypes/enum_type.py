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

"""Build C++ header models for enums with model-defined integer storage."""

from typing import cast

from score.ecu_model.data_types.enum import EnumDataType
from score.generators.src.common.common_utils import generate_header_file_guard
from score.generators.src.datatypes.cpp_model import CppEnum, CppEnumerator, CppHeaderModel
from score.generators.src.datatypes.cpp_type_registry import CppTypeRegistry


def build_enum_header(datatype: EnumDataType, registry: CppTypeRegistry) -> CppHeaderModel:
    """Flatten inherited enumerators and validate the complete scoped enum declaration."""
    if datatype.name is None:
        raise ValueError("Enums require a declared name")

    if datatype.size not in (8, 16, 32, 64):
        raise ValueError(f"Unsupported enum storage size {datatype.size}: {datatype.fully_qualified_name}")
    underlying_type = f"std::{'int' if datatype.signed else 'uint'}{datatype.size}_t"
    minimum_value = -(1 << (datatype.size - 1)) if datatype.signed else 0
    maximum_value = (1 << (datatype.size - int(datatype.signed))) - 1

    values = []
    for enumerator in datatype.values:
        value = enumerator.value
        if value is None:
            raise ValueError(
                f"Missing numeric value for enum literal: {datatype.fully_qualified_name}.{enumerator.name}"
            )
        values.append(CppEnumerator(enumerator.name.as_str, value))

    parent = datatype.extends
    if parent is not None:
        if not isinstance(parent, EnumDataType):
            raise ValueError(f"Unresolved enum inheritance reference: {datatype.fully_qualified_name}")
        parent_header = cast(CppHeaderModel, registry.named_types[parent.fully_qualified_name].header_model)
        values.extend(cast(CppEnum, parent_header.declaration).values)

    if not values:
        raise ValueError(f"Enums require at least one enumerator: {datatype.fully_qualified_name}")

    names = set()
    numeric_values = set()
    for enumerator in values:
        if enumerator.name in names:
            raise ValueError(f"Duplicate enum literal name: {datatype.fully_qualified_name}.{enumerator.name}")
        if enumerator.value in numeric_values and not datatype.allow_value_aliases:
            raise ValueError(
                f"Enum value aliases are not allowed: "
                f"{datatype.fully_qualified_name}.{enumerator.name} = {enumerator.value}"
            )
        if not minimum_value <= enumerator.value <= maximum_value:
            raise ValueError(
                f"Enum value outside {underlying_type} range: "
                f"{datatype.fully_qualified_name}.{enumerator.name} = {enumerator.value}"
            )
        names.add(enumerator.name)
        numeric_values.add(enumerator.value)

    name = datatype.name.as_str
    namespaces = tuple(segment.as_str for segment in datatype.namespace)
    type_info = registry.register_named_type(datatype.fully_qualified_name, name, namespaces)
    path = type_info.required_includes[0]
    header = CppHeaderModel(
        path=path,
        guard=generate_header_file_guard(path),
        namespaces=namespaces,
        includes=("<cstdint>",),
        declaration=CppEnum(name, underlying_type, tuple(values)),
    )
    type_info.header_model = header
    return header
