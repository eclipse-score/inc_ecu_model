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

from score.ecu_model.data_types.common import DataTypeBase
from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.model import ModelElement
from score.generators.src.datatypes.cpp_model import CppHeaderModel
from score.generators.src.datatypes.cpp_type_registry import CppTypeInfo, CppTypeRegistry
from score.generators.src.datatypes.primitive_type import register_primitive
from score.generators.src.datatypes.typedef_type import build_alias_header


class _ProcessingState(Enum):
    """Track whether a named datatype is being lowered or has completed."""

    IN_PROGRESS = auto()
    COMPLETE = auto()


class DatatypeUtils:
    """Lower supported datatypes and notify the caller for each completed header."""

    @staticmethod
    def build_type_registry(
        selected_datatypes: Iterable[ModelElement | PrimitiveDataType],
        on_header_ready: Callable[[CppHeaderModel], None],
    ) -> CppTypeRegistry:
        """Register supported datatypes in dependency order, rejecting unsupported input."""
        registry = CppTypeRegistry()
        states: dict[UUID, _ProcessingState] = {}
        active_path: list[TypedefDataType] = []

        def process(datatype: ModelElement | PrimitiveDataType | Identifier | QualifiedName) -> CppTypeInfo:
            if isinstance(datatype, (Identifier, QualifiedName)):
                raise ValueError(f"Unresolved datatype reference: {datatype}")
            if isinstance(datatype, PrimitiveDataType):
                return register_primitive(datatype, registry)
            if not isinstance(datatype, DataTypeBase):
                raise TypeError(f"Expected a datatype, got {type(datatype).__name__}")
            # TODO: Add support for other datatype kinds in the future.
            if not isinstance(datatype, TypedefDataType):
                name = datatype.fully_qualified_name if datatype.name is not None else "<anonymous>"
                raise NotImplementedError(f"Unsupported datatype: {name} ({datatype.kind})")

            identity = datatype.id
            state = states.get(identity)
            if state is _ProcessingState.COMPLETE:
                return registry.named_types[datatype.fully_qualified_name]
            if state is _ProcessingState.IN_PROGRESS:
                cycle_start = next(index for index, entry in enumerate(active_path) if entry.id == identity)
                dependency_chain = " -> ".join(
                    entry.fully_qualified_name for entry in (*active_path[cycle_start:], datatype)
                )
                raise ValueError(f"Cyclic datatype dependency detected: {dependency_chain}")
            states[identity] = _ProcessingState.IN_PROGRESS
            active_path.append(datatype)
            try:
                target_info = process(datatype.data_type)
                header = build_alias_header(datatype, target_info, registry)
                on_header_ready(header)
                states[identity] = _ProcessingState.COMPLETE
                return registry.named_types[datatype.fully_qualified_name]
            finally:
                active_path.pop()

        for datatype in selected_datatypes:
            process(datatype)
        return registry
