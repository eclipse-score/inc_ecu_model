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

"""Build C++ header models for named typedefs."""

from score.ecu_model.data_types.typedef import TypedefDataType
from score.generators.src.common.common_utils import generate_header_file_guard
from score.generators.src.datatypes.cpp_model import CppAlias, CppHeaderModel
from score.generators.src.datatypes.cpp_type_registry import CppTypeInfo, CppTypeRegistry


def build_alias_header(
    datatype: TypedefDataType, target_info: CppTypeInfo, registry: CppTypeRegistry
) -> CppHeaderModel:
    """Build a typedef header using its processed target's C++ usage information."""
    if datatype.name is None:
        raise ValueError("Typedefs require a declared name")

    name = datatype.name.as_str
    namespaces = tuple(segment.as_str for segment in datatype.namespace)
    type_info = registry.register_named_type(datatype.fully_qualified_name, name, namespaces)
    path = type_info.required_includes[0]
    return CppHeaderModel(
        path=path,
        guard=generate_header_file_guard(path),
        namespaces=namespaces,
        includes=tuple(sorted(set(target_info.required_includes))),
        declaration=CppAlias(name, target_info.cpp_type_name),
    )
