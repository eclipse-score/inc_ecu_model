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

"""Compute member-owned SOME/IP layouts from resolved ECU model objects."""

import logging
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from score.ecu_model.communication.service_interface import Attribute, Broadcast, Method, ServiceInterface
from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.common import DataTypeBase, DataTypeOrReference
from score.ecu_model.data_types.composite import DataTypeField
from score.ecu_model.data_types.enum import EnumDataType
from score.ecu_model.data_types.map import MapDataType
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.data_types.union import UnionDataType
from score.generators.src.common.array_bounds import effective_bounds
from score.generators.src.layout.element_layout import ByteOrder, ElementLayout, StringEncoding

_LOG = logging.getLogger(__name__)
type _Member = Attribute | Method | Broadcast
type _Properties = Mapping[str, Any]
type _StringConfig = tuple[StringEncoding, ByteOrder | None, int]

_ATTRIBUTE_ENDIAN_PROPERTY = "SomeIpAttributeEndianess"
_METHOD_ENDIAN_PROPERTY = "SomeIpMethodEndianess"
_BROADCAST_ENDIAN_PROPERTY = "SomeIpBroadcastEndianess"
_STRUCT_LENGTH_WIDTH_PROPERTY = "SomeIpStructLengthWidth"
_ARRAY_LENGTH_WIDTH_PROPERTY = "SomeIpArrayLengthWidth"
_STRING_ENCODING_PROPERTY = "SomeIpStringEncoding"
_STRING_LENGTH_WIDTH_PROPERTY = "SomeIpStringLengthWidth"
_LITTLE_ENDIAN_DEPLOYMENT_VALUE = "le"
_STRING_ENCODINGS = {
    "utf8": (StringEncoding.UTF8, None),
    "utf16le": (StringEncoding.UTF16, ByteOrder.LITTLE_ENDIAN),
    "utf16be": (StringEncoding.UTF16, ByteOrder.BIG_ENDIAN),
    "ucs2": (StringEncoding.UTF16, ByteOrder.BIG_ENDIAN),
}


def calculate_interface_layouts(service_interface: ServiceInterface) -> dict[UUID, ElementLayout]:
    """Map declared member IDs to interned layouts without modifying the model."""
    layouts: dict[UUID, ElementLayout] = {}
    design = service_interface.design_element
    for members, deployments, endian_property in (
        (design.attributes, service_interface.attribute_deployment_properties, _ATTRIBUTE_ENDIAN_PROPERTY),
        (design.methods, service_interface.method_deployment_properties, _METHOD_ENDIAN_PROPERTY),
        (design.broadcasts, service_interface.broadcast_deployment_properties, _BROADCAST_ENDIAN_PROPERTY),
    ):
        for member in members.values():
            if isinstance(member, Method):
                arguments = member.inputs + member.outputs
            elif isinstance(member, Broadcast):
                arguments = member.outputs
            elif isinstance(member, Attribute):
                arguments = []
            else:
                raise TypeError(f"Unsupported layout member {type(member).__name__}")
            layouts[member.id] = _calculate_member_layout(
                member,
                deployments[member.name],
                endian_property,
                arguments,
                f"{design.fully_qualified_name}.{member.name.as_str}",
            )
    return layouts


def _calculate_member_layout(
    member: _Member,
    properties: _Properties,
    endian_property: str,
    arguments: Sequence[DataTypeField],
    member_fqn: str,
) -> ElementLayout:
    """Return an interned layout without modifying the deployment or design model."""
    byte_order = (
        ByteOrder.LITTLE_ENDIAN
        if properties.get(endian_property) == _LITTLE_ENDIAN_DEPLOYMENT_VALUE
        else ByteOrder.BIG_ENDIAN
    )
    traversal = _DataTypeLayoutTraversal()
    if isinstance(member, Attribute):
        # Inline arrays use the attribute deployment as their declaration-owner configuration.
        vector_bytes = traversal.array_width(member.data_type, properties)
        string_config = traversal.pick_strings(
            [
                traversal.local_string(properties),
                traversal.string_type(member.data_type, properties, fqn=member_fqn),
            ],
            member_fqn,
        )
    else:
        vector_bytes = traversal.array_fields(arguments)
        string_config = traversal.string_fields(arguments, member_fqn)

    if string_config is not None and string_config[1] is not None and string_config[1] != byte_order:
        raise RuntimeError(
            f"conflicting endianess provided for {type(member).__name__}: {member_fqn} "
            "and string encoding of the same element."
        )

    struct_bytes = 0
    if isinstance(member, Attribute) and _attribute_is_struct(member):
        value = properties.get(_STRUCT_LENGTH_WIDTH_PROPERTY, 0)
        if value is None:
            raise TypeError(f"{_STRUCT_LENGTH_WIDTH_PROPERTY} must be an int")
        struct_bytes = value

    return ElementLayout.intern(
        byte_order=byte_order,
        vector_length_field_bytes=4 if vector_bytes is None else vector_bytes,
        string_length_field_bytes=4 if string_config is None else string_config[2],
        struct_length_field_bytes=struct_bytes,
        string_encoding=StringEncoding.UTF8 if string_config is None else string_config[0],
    )


def _attribute_is_struct(attribute: Attribute) -> bool:
    data_type = attribute.data_type
    return isinstance(data_type, StructDataType) or (
        isinstance(data_type, ArrayDataType) and data_type.is_inline and isinstance(data_type.data_type, StructDataType)
    )


def _data_type_fqn(data_type: DataTypeBase, fallback_fqn: str) -> str:
    return data_type.fully_qualified_name if data_type.name is not None else fallback_fqn


class _DataTypeLayoutTraversal:
    """Preserve legacy reference/use-site distinctions while visiting shared types."""

    def __init__(self) -> None:
        self._active: set[UUID] = set()

    @contextmanager
    def visit(self, data_type: DataTypeOrReference) -> Generator[None]:
        if not isinstance(data_type, (DataTypeBase, PrimitiveDataType)):
            raise ValueError(f"Unsupported unresolved layout type reference: {data_type!r}")
        if isinstance(data_type, PrimitiveDataType):
            yield
            return
        identity = data_type.id
        if identity in self._active:
            raise ValueError("Recursive type graphs are not supported by layout calculation")
        self._active.add(identity)
        try:
            yield
        finally:
            self._active.remove(identity)

    def array_fields(self, fields: Sequence[DataTypeField]) -> int | None:
        for field in fields:
            value = self.array_width(field.data_type, field.deployment_properties)
            if value is not None:
                return value
        return None

    def array_width(self, data_type: DataTypeOrReference, use_properties: _Properties | None = None) -> int | None:
        with self.visit(data_type):
            if isinstance(data_type, (PrimitiveDataType, EnumDataType)):
                return None
            if isinstance(data_type, TypedefDataType):
                return self.array_width(data_type.data_type)
            if isinstance(data_type, ArrayDataType):
                properties = (
                    use_properties
                    if data_type.is_inline and use_properties is not None
                    else data_type.deployment_properties
                )
                if data_type.is_inline:
                    if isinstance(data_type.data_type, PrimitiveDataType):
                        return properties.get(_ARRAY_LENGTH_WIDTH_PROPERTY)
                    return self.array_width(data_type.data_type)
                minimum, maximum = effective_bounds(
                    data_type,
                    data_type.deployment_properties,
                    _data_type_fqn(data_type, "<inline array>"),
                )
                width = properties.get(_ARRAY_LENGTH_WIDTH_PROPERTY)
                if maximum != 0 and minimum == maximum and width is None:
                    return self.array_width(data_type.data_type)
                return width
            if isinstance(data_type, StructDataType):
                if data_type.extends is not None:
                    width = self.array_width(data_type.extends)
                    if width is not None:
                        return width
                return self.array_fields(data_type.fields)
            if isinstance(data_type, UnionDataType):
                return self.array_fields(self.composite_fields(data_type))
            if isinstance(data_type, MapDataType):
                width = self.array_width(data_type.key_type)
                return width if width is not None else self.array_width(data_type.value_type)
            raise TypeError(f"Unsupported layout type {type(data_type).__name__}")

    @staticmethod
    def local_string(properties: _Properties) -> _StringConfig | None:
        encoding = properties.get(_STRING_ENCODING_PROPERTY)
        if not encoding:
            return None
        if not isinstance(encoding, str) or encoding not in _STRING_ENCODINGS:
            raise ValueError(f"Unsupported {_STRING_ENCODING_PROPERTY} {encoding!r}")
        string_encoding, byte_order = _STRING_ENCODINGS[encoding]
        width = properties[_STRING_LENGTH_WIDTH_PROPERTY]
        return string_encoding, byte_order, width

    @staticmethod
    def pick_strings(values: Sequence[_StringConfig | None], fqn: str) -> _StringConfig | None:
        candidates = [value for value in values if value is not None]
        if not candidates:
            return None
        if any(value != candidates[0] for value in candidates[1:]):
            _LOG.warning("conflicting string encodings for %s: %s", fqn, candidates)
        return candidates[0]

    def string_fields(self, fields: Sequence[DataTypeField], fqn: str) -> _StringConfig | None:
        candidates = []
        for field in fields:
            field_fqn = f"{fqn}.{field.name.as_str}"
            data_type = field.data_type
            if isinstance(data_type, ArrayDataType) and data_type.is_inline:
                nested = self.string_type(data_type.data_type, fqn=field_fqn)
            else:
                nested = self.string_type(data_type, fqn=field_fqn)
            candidates.append(self.pick_strings([self.local_string(field.deployment_properties), nested], field_fqn))
        return self.pick_strings(candidates, fqn)

    def string_type(
        self,
        data_type: DataTypeOrReference,
        use_properties: _Properties | None = None,
        *,
        fqn: str,
    ) -> _StringConfig | None:
        with self.visit(data_type):
            if isinstance(data_type, DataTypeBase):
                fqn = _data_type_fqn(data_type, fqn)
            if isinstance(data_type, (PrimitiveDataType, EnumDataType)):
                return None
            if isinstance(data_type, ArrayDataType):
                properties = (
                    use_properties
                    if data_type.is_inline and use_properties is not None
                    else data_type.deployment_properties
                )
                if data_type.data_type is PrimitiveDataType.STRING:
                    return self.local_string(properties)
                return self.string_type(data_type.data_type, fqn=fqn)
            if isinstance(data_type, TypedefDataType):
                if data_type.data_type is PrimitiveDataType.STRING:
                    return self.local_string(data_type.deployment_properties)
                return self.string_type(data_type.data_type, fqn=fqn)
            if isinstance(data_type, (StructDataType, UnionDataType)):
                return self.string_fields(self.composite_fields(data_type), data_type.fully_qualified_name)
            if isinstance(data_type, MapDataType):
                return self.string_map(data_type, fqn)
            raise TypeError(f"Unsupported layout type {type(data_type).__name__}")

    def string_map(self, data_type: MapDataType, fqn: str) -> _StringConfig | None:
        fqn = _data_type_fqn(data_type, fqn)
        key_string = data_type.key_type is PrimitiveDataType.STRING
        value_string = data_type.value_type is PrimitiveDataType.STRING
        if key_string and value_string:
            return self.local_string(data_type.deployment_properties)
        if key_string or value_string:
            other_fqn = f"{fqn}.value" if key_string else f"{fqn}.key"
            other = data_type.value_type if key_string else data_type.key_type
            nested = self.string_type(other, fqn=other_fqn)
            if nested is not None:
                return self.pick_strings([self.local_string(data_type.deployment_properties), nested], fqn)
        candidates = []
        for role, value in (("key", data_type.key_type), ("value", data_type.value_type)):
            if isinstance(value, PrimitiveDataType):
                continue
            if not isinstance(value, DataTypeBase):
                raise ValueError(f"Unresolved layout type reference {value}")
            value_fqn = _data_type_fqn(value, f"{fqn}.{role}")
            nested = self.string_type(value, fqn=value_fqn)
            candidates.append(self.pick_strings([self.local_string(value.deployment_properties), nested], value_fqn))
        return self.pick_strings(candidates, fqn)

    def composite_fields(self, data_type: StructDataType | UnionDataType) -> tuple[DataTypeField, ...]:
        fields = data_type.fields
        if data_type.extends is None:
            return fields
        base = data_type.extends
        if not isinstance(base, type(data_type)):
            raise ValueError("Unresolved or invalid composite base type")
        with self.visit(base):
            inherited = self.composite_fields(base)
        return inherited + fields if isinstance(data_type, StructDataType) else fields + inherited
