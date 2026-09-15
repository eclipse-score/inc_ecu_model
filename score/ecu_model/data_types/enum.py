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
from __future__ import annotations

from pydantic import Field, ValidationInfo, field_validator
from typing import Literal

from score.ecu_model.data_types.common import (
    DataTypeBase,
    DataTypeKind,
    DataTypeReference,
    DataTypeSource,
    Identifier,
)
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.model import ModelElement


class EnumValue(ModelElement):
    """A named enum literal with an optional numeric value."""

    name: Identifier = Field(
        description="Identifier of the enum literal in its source namespace",
    )
    # TODO: value can be < 0 currently, because theoretically FRANCA allows for such a specification,
    # but it makes no sense, assuming several code generators work on the data and each would have to decide
    # on it's own interpretation of negative values.
    value: int | None = Field(
        default=None,
        description="Optional numeric value assigned to the enum literal; "
        "may be negative, e.g. Franca allows signed enumerator expressions",
    )

    @field_validator("value", mode="before")
    @classmethod
    def _reject_boolean_values(cls, value: int | bool | None) -> int | None:
        """Reject booleans so they are not silently converted to 1 or 0."""
        if isinstance(value, bool):
            raise ValueError("enum value must be an integer, not boolean")
        return value

    def finalize(self) -> None:
        raise NotImplementedError("finalize method must be implemented by subclasses")


class EnumDataType(DataTypeBase):
    """A declared enum data type with named literals."""

    kind: Literal[DataTypeKind.ENUM] = Field(default=DataTypeKind.ENUM, frozen=True)
    extends: EnumDataType | DataTypeReference | None = Field(
        default=None,
        description="Optional enum definition extended by this enum; "
        "may temporarily be an unresolved reference during model resolution",
    )
    underlying_type: PrimitiveDataType = Field(
        default=PrimitiveDataType.UINT32,
        description="Primitive type used for enum storage",
    )
    values: tuple[EnumValue, ...] = Field(
        default_factory=tuple,
        description="Named enum literals, not changeable after creation",
    )

    @field_validator("values")
    @classmethod
    def _validate_value_definitions(cls, values: tuple[EnumValue, ...]) -> tuple[EnumValue, ...]:
        """Validate enum literal value definitions and uniqueness."""
        has_explicit_values = any(enum_value.value is not None for enum_value in values)
        has_implicit_values = any(enum_value.value is None for enum_value in values)
        if has_explicit_values and has_implicit_values:
            raise ValueError("enum values must either all be explicitly defined or all be omitted")
        identifiers = [enum_value.name for enum_value in values]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("enum value identifiers must be unique")
        explicit_values = [enum_value.value for enum_value in values if enum_value.value is not None]
        if len(explicit_values) != len(set(explicit_values)):
            raise ValueError("explicit enum values must be unique")
        return values

    @field_validator("extends")
    @classmethod
    def _validate_inheritance(
        cls, extends: EnumDataType | DataTypeReference | None, info: ValidationInfo
    ) -> EnumDataType | DataTypeReference | None:
        """Validate enum inheritance according to its enclosing source language."""
        if extends is not None:
            source_kind = info.data.get("source_kind")
            if source_kind != DataTypeSource.FRANCA:
                raise ValueError(f"Enum inheritance is only allowed for FRANCA source kind, but got {source_kind}")
        return extends
