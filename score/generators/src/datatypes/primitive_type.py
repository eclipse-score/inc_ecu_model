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

"""Map supported builtin primitives to C++ usage information."""

from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.generators.src.datatypes.cpp_type_registry import CppTypeInfo, CppTypeRegistry

_PRIMITIVE_CPP_TYPES = {
    PrimitiveDataType.STRING: ("std::string", ("<string>",)),
    PrimitiveDataType.BOOL: ("bool", ()),
    PrimitiveDataType.FLOAT: ("float", ()),
    PrimitiveDataType.DOUBLE: ("double", ()),
    PrimitiveDataType.UINT8: ("std::uint8_t", ("<cstdint>",)),
    PrimitiveDataType.UINT16: ("std::uint16_t", ("<cstdint>",)),
    PrimitiveDataType.UINT32: ("std::uint32_t", ("<cstdint>",)),
    PrimitiveDataType.UINT64: ("std::uint64_t", ("<cstdint>",)),
    PrimitiveDataType.INT8: ("std::int8_t", ("<cstdint>",)),
    PrimitiveDataType.INT16: ("std::int16_t", ("<cstdint>",)),
    PrimitiveDataType.INT32: ("std::int32_t", ("<cstdint>",)),
    PrimitiveDataType.INT64: ("std::int64_t", ("<cstdint>",)),
}


def register_primitive(datatype: PrimitiveDataType, registry: CppTypeRegistry) -> CppTypeInfo:
    """Reuse one usage entry for each supported builtin primitive."""
    if datatype not in registry.primitive_types:
        if datatype not in _PRIMITIVE_CPP_TYPES:
            raise NotImplementedError(f"Unsupported primitive datatype: {datatype.value}")
        cpp_type, required_includes = _PRIMITIVE_CPP_TYPES[datatype]
        registry.primitive_types[datatype] = CppTypeInfo(
            source_type_name=datatype.value,
            cpp_type_name=cpp_type,
            required_includes=required_includes,
        )
    return registry.primitive_types[datatype]
