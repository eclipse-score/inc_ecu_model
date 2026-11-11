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

from typing import Any

from pydantic import Field, ValidationInfo, field_validator

from score.ecu_model.data_types.common import (
    DataTypeBase,
    DataTypeOrReference,
    DataTypeReference,
    DataTypeSource,
    Identifier,
)
from score.ecu_model.model import ModelElement


class DataTypeField(ModelElement):
    """A named member of a composite data type, e.g. a struct."""

    name: Identifier = Field(
        description="Identifier of the field in its declaring data type, validated in the using struct or union",
    )
    data_type: DataTypeOrReference = Field(
        description="Builtin primitive or reference to the declared data type of the field; "
        "may temporarily be an unresolved reference during model resolution",
    )
    field_number: int | None = Field(
        default=None,
        description="Optional wire tag defined by the source IDL, e.g. the protobuf field number",
    )
    optional: bool = Field(
        default=False,
        description="Whether the field may be absent, e.g. a proto2 or Franca optional field",
    )
    default: str | None = Field(
        default=None,
        description="Optional default value carried over from the source IDL, serialized as string",
    )
    deployment_properties: dict[str, object] = Field(
        default_factory=dict,
        description="Deployment properties aggregated from all communication bindings using this field",
    )

    @field_validator("field_number", mode="before")
    @classmethod
    def _reject_non_positive_field_numbers(cls, value: int | bool | None) -> int | None:
        """Reject booleans and non-positive numbers so they are not silently accepted as wire tags."""
        if isinstance(value, bool):
            raise ValueError("field number must be an integer, not boolean")
        if value is not None and value <= 0:
            raise ValueError("field number must be positive")
        return value


class CompositeDataType(DataTypeBase):
    """Shared metadata for declared data types that are made up of named fields, i.e. structs and unions."""

    extends: DataTypeBase | DataTypeReference | None = Field(
        default=None,
        description="Optional data type definition extended by this data type; "
        "may temporarily be an unresolved reference during model resolution",
    )
    fields: tuple[DataTypeField, ...] = Field(
        default_factory=tuple,
        description="Fields in source declaration order, not changeable after creation",
    )

    def model_post_init(self, context: Any, /) -> None:
        """Reject instantiation of this abstract base, before the element is added to the model registry."""
        if type(self) is CompositeDataType:
            raise TypeError("CompositeDataType is abstract, instantiate a concrete data type like StructDataType")
        super().model_post_init(context)

    @field_validator("fields")
    @classmethod
    def _validate_field_definitions(
        cls,
        fields: tuple[DataTypeField, ...],
    ) -> tuple[DataTypeField, ...]:
        """Validate field definitions and uniqueness."""
        identifiers = [field.name for field in fields]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("field identifiers must be unique")
        field_numbers = [field.field_number for field in fields if field.field_number is not None]
        if len(field_numbers) != len(set(field_numbers)):
            raise ValueError("explicit field numbers must be unique")
        return fields

    @field_validator("extends")
    @classmethod
    def _validate_inheritance(
        cls, extends: DataTypeBase | DataTypeReference | None, info: ValidationInfo
    ) -> DataTypeBase | DataTypeReference | None:
        """Validate the inheritance according to their enclosing source language and kind."""
        if extends is not None:
            source_kind = info.data.get("source_kind")
            # TODO: franca specific inheritence should be handled by the parser and not in the idl independent model
            if source_kind != DataTypeSource.FRANCA:
                raise ValueError(
                    f"{cls.__name__} inheritance is only allowed for FRANCA source kind, but got {source_kind}"
                )
            if isinstance(extends, DataTypeReference):
                return extends
            expected_kind = info.data.get("kind")
            if extends.kind != expected_kind:
                raise ValueError(
                    f"{cls.__name__} can only extend another data type of kind '{expected_kind}', "
                    f"but referenced base type '{extends.id}' is of kind '{extends.kind}'"
                )
        return extends
