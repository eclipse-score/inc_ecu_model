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

"""Coordinate datatype lowering and notify callers of completed headers."""

from collections.abc import Callable, Iterable
from enum import Enum, auto
from uuid import UUID

from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.common import DataType, DataTypeBase, DataTypeOrReference
from score.ecu_model.data_types.enum import EnumDataType
from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.data_types.union import UnionDataType
from score.generators.src.datatypes.array_type import build_array_header
from score.generators.src.datatypes.cpp_model import CppHeaderModel
from score.generators.src.datatypes.cpp_type_registry import CppTypeInfo, CppTypeRegistry
from score.generators.src.datatypes.enum_type import build_enum_header
from score.generators.src.datatypes.primitive_type import register_primitive
from score.generators.src.datatypes.struct_type import build_struct_header
from score.generators.src.datatypes.typedef_type import build_alias_header
from score.generators.src.datatypes.union_type import build_union_header


class _ProcessingState(Enum):
    """Track whether a datatype is being lowered or has completed."""

    IN_PROGRESS = auto()
    COMPLETE = auto()


class DatatypeUtils:
    """Lower supported datatypes and notify the caller for each completed header."""

    @staticmethod
    def build_type_registry(
        selected_datatypes: Iterable[DataType],
        on_header_ready: Callable[[CppHeaderModel], None],
    ) -> CppTypeRegistry:
        """Register supported datatypes in dependency order, rejecting unsupported input."""
        registry = CppTypeRegistry()
        states: dict[UUID, _ProcessingState] = {}
        active_path: list[DataTypeBase] = []

        def require_resolved_datatype(datatype: DataTypeOrReference) -> DataType:
            """Reject unresolved references before they enter datatype lowering."""
            if isinstance(datatype, (Identifier, QualifiedName)):
                raise ValueError(f"Unresolved datatype reference: {datatype}")
            return datatype

        def process(datatype: DataType) -> CppTypeInfo | None:
            if isinstance(datatype, PrimitiveDataType):
                return register_primitive(datatype, registry)
            if not isinstance(datatype, (ArrayDataType, TypedefDataType, EnumDataType, StructDataType, UnionDataType)):
                raise NotImplementedError(f"Unsupported datatype: {type(datatype).__name__}")

            identity = datatype.id
            state = states.get(identity)
            if state is _ProcessingState.COMPLETE:
                if isinstance(datatype, ArrayDataType) and datatype.is_inline:
                    return None
                return registry.named_types[datatype.fully_qualified_name]
            if state is _ProcessingState.IN_PROGRESS:
                cycle_start = next(index for index, entry in enumerate(active_path) if entry.id == identity)
                dependency_chain = " -> ".join(
                    "<inline array>"
                    if isinstance(entry, ArrayDataType) and entry.is_inline
                    else entry.fully_qualified_name
                    for entry in (*active_path[cycle_start:], datatype)
                )
                raise ValueError(f"Cyclic datatype dependency detected: {dependency_chain}")
            states[identity] = _ProcessingState.IN_PROGRESS
            active_path.append(datatype)
            try:
                if isinstance(datatype, ArrayDataType):
                    process(require_resolved_datatype(datatype.data_type))
                    if datatype.is_inline:
                        states[identity] = _ProcessingState.COMPLETE
                        return None
                    header = build_array_header(datatype, registry)
                elif isinstance(datatype, TypedefDataType):
                    if isinstance(datatype.data_type, ArrayDataType) and datatype.data_type.is_inline:
                        raise NotImplementedError(
                            f"Inline array typedef targets are currently not supported: {datatype.fully_qualified_name}"
                        )
                    target_info = process(require_resolved_datatype(datatype.data_type))
                    header = build_alias_header(datatype, target_info, registry)
                elif isinstance(datatype, EnumDataType):
                    if datatype.extends is not None:
                        process(require_resolved_datatype(datatype.extends))
                    header = build_enum_header(datatype, registry)
                elif isinstance(datatype, StructDataType):
                    if datatype.extends is not None:
                        process(require_resolved_datatype(datatype.extends))
                    for member in datatype.fields:
                        process(require_resolved_datatype(member.data_type))
                    header = build_struct_header(datatype, registry)
                else:
                    if datatype.extends is not None:
                        process(require_resolved_datatype(datatype.extends))
                    for member in datatype.fields:
                        process(require_resolved_datatype(member.data_type))
                    header = build_union_header(datatype, registry)
                on_header_ready(header)
                states[identity] = _ProcessingState.COMPLETE
                return registry.named_types[datatype.fully_qualified_name]
            finally:
                active_path.pop()

        for datatype in selected_datatypes:
            process(require_resolved_datatype(datatype))
        return registry
