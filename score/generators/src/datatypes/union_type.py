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

"""Build C++ header models for unions."""

from typing import cast

from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.union import UnionDataType
from score.generators.src.common.common_utils import generate_header_file_guard
from score.generators.src.datatypes.array_type import get_array_type_info
from score.generators.src.datatypes.cpp_model import CppHeaderModel, CppVariant
from score.generators.src.datatypes.cpp_type_registry import CppTypeRegistry


def build_union_header(datatype: UnionDataType, registry: CppTypeRegistry) -> CppHeaderModel:
    """Append cached inherited alternatives after local ones, preserving repeated types."""
    if datatype.name is None:
        raise ValueError("Unions require a declared name")
    name = datatype.name.as_str
    namespaces = tuple(segment.as_str for segment in datatype.namespace)
    type_info = registry.register_named_type(datatype.fully_qualified_name, name, namespaces)
    path = type_info.required_includes[0]
    alternatives = []
    includes = {"<variant>"}
    for member in datatype.fields:
        if isinstance(member.data_type, PrimitiveDataType):
            member_type = registry.primitive_types[member.data_type]
        elif isinstance(member.data_type, ArrayDataType):
            member_type = get_array_type_info(
                member.data_type,
                registry,
                member.deployment_properties,
                f"{datatype.fully_qualified_name}.{member.name.as_str}",
            )
        else:
            member_type = registry.named_types[member.data_type.fully_qualified_name]
        alternatives.append(member_type.cpp_type_name)
        includes.update(member_type.required_includes)

    parent = datatype.extends
    if parent is not None:
        parent_header = cast(CppHeaderModel, registry.named_types[parent.fully_qualified_name].header_model)
        alternatives.extend(cast(CppVariant, parent_header.declaration).alternatives)
        includes.update(parent_header.includes)

    if not alternatives:
        raise ValueError(f"Unions require at least one alternative: {datatype.fully_qualified_name}")

    header = CppHeaderModel(
        path=path,
        guard=generate_header_file_guard(path),
        namespaces=namespaces,
        includes=tuple(sorted(includes)),
        declaration=CppVariant(name, tuple(alternatives)),
    )
    type_info.header_model = header
    return header
