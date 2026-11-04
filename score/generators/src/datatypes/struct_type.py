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

"""Build C++ header models for supported structs."""

from typing import cast

from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.generators.src.common.common_utils import generate_header_file_guard
from score.generators.src.datatypes.cpp_model import CppField, CppHeaderModel, CppStruct
from score.generators.src.datatypes.cpp_type_registry import CppTypeRegistry


def build_struct_header(datatype: StructDataType, registry: CppTypeRegistry) -> CppHeaderModel:
    """Flatten inherited fields after parent and field dependencies have completed."""
    if datatype.name is None:
        raise ValueError("Structs require a declared name")

    name = datatype.name.as_str
    namespaces = tuple(segment.as_str for segment in datatype.namespace)
    type_info = registry.register_named_type(datatype.fully_qualified_name, name, namespaces)
    path = type_info.required_includes[0]
    fields = []
    includes = set()
    for member in datatype.fields:
        if isinstance(member.data_type, PrimitiveDataType):
            member_type = registry.primitive_types[member.data_type]
            generated_type_alias = None
        else:
            member_type = registry.named_types[member.data_type.fully_qualified_name]
            generated_type_alias = f"{member.name.as_str}_generated_type"
        fields.append(CppField(member.name.as_str, member_type.cpp_type_name, generated_type_alias))
        includes.update(member_type.required_includes)

    parent = datatype.extends
    if parent is not None:
        parent_header = cast(CppHeaderModel, registry.named_types[parent.fully_qualified_name].header_model)
        fields.extend(cast(CppStruct, parent_header.declaration).fields)
        includes.update(parent_header.includes)

    names = set()
    for member in fields:
        if member.name in names:
            raise ValueError(f"Duplicate struct field name: {datatype.fully_qualified_name}.{member.name}")
        names.add(member.name)

    header = CppHeaderModel(
        path=path,
        guard=generate_header_file_guard(path),
        namespaces=namespaces,
        includes=tuple(sorted(includes)),
        declaration=CppStruct(name, tuple(fields)),
    )
    type_info.header_model = header
    return header
