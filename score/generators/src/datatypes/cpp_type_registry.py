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

"""Generation-local C++ type identities and usage information."""

from dataclasses import dataclass, field

from score.ecu_model.data_types.primitives import PrimitiveDataType


@dataclass
class CppTypeInfo:
    """C++ type spelling and includes required to use a datatype."""

    source_type_name: str
    cpp_type_name: str
    required_includes: tuple[str, ...]


@dataclass
class CppTypeRegistry:
    """Keep named and primitive identities distinct within one generation."""

    named_types: dict[str, CppTypeInfo] = field(default_factory=dict)
    primitive_types: dict[PrimitiveDataType, CppTypeInfo] = field(default_factory=dict)

    def register_named_type(self, source_type_name: str, name: str, namespaces: tuple[str, ...]) -> CppTypeInfo:
        """Register a named type's C++ spelling and header, rejecting name conflicts."""
        if source_type_name in self.named_types:
            return self.named_types[source_type_name]
        cpp_namespace = "::" + "::".join(namespaces) if namespaces else ""
        for existing in self.named_types.values():
            existing_namespace, _, existing_name = existing.cpp_type_name.rpartition("::")
            if existing_namespace == cpp_namespace and existing_name.casefold() == name.casefold():
                raise ValueError(
                    f"Case-insensitive type name conflict: {existing.source_type_name}, {source_type_name}"
                )
        path = "/".join((*namespaces, name + ".h"))
        type_info = CppTypeInfo(source_type_name, f"{cpp_namespace}::{name}", (path,))
        self.named_types[source_type_name] = type_info
        return type_info
