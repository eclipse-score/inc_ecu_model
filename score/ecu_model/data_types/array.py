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

from typing import Literal

from pydantic import Field, field_validator, model_validator

from score.ecu_model.data_types.common import (
    DataType,
    DataTypeBase,
    DataTypeKind,
    DataTypeOrReference,
)


class ArrayDataType(DataTypeBase):
    """Definition of an array data type with element type and optional dimensions."""

    kind: Literal[DataTypeKind.ARRAY] = Field(default=DataTypeKind.ARRAY, frozen=True)
    data_type: DataTypeOrReference = Field(
        description="Array element type definition; may temporarily be an unresolved reference during model resolution",
    )
    is_inline: bool = Field(
        default=False,
        description="Whether the array is declared inline without a type name",
    )
    dimension_min: int | None = Field(
        default=None,
        description="Minimum dimension bound",
    )
    dimension_max: int | None = Field(
        default=None,
        description="Maximum dimension bound",
    )

    @field_validator("dimension_min", "dimension_max")
    @classmethod
    def _validate_dimension_bound_is_non_negative(cls, value: int | None) -> int | None:
        """Validate array dimension bounds as non-negative integers when provided."""
        if value is not None and value < 0:
            raise ValueError("array dimension bounds must be non-negative")
        return value

    @model_validator(mode="after")
    def _validate_array_constraints(self) -> ArrayDataType:
        """Validate array naming and dimension constraints."""
        if self.is_inline and self.name is not None:
            raise ValueError("inline arrays must not have an identifier")
        if not self.is_inline and self.name is None:
            raise ValueError("non-inline arrays require an identifier")
        if (
            self.dimension_min is not None
            and self.dimension_max is not None
            and self.dimension_min > self.dimension_max
        ):
            raise ValueError("dimension_min must not be greater than dimension_max")
        return self

    def finalize(self) -> None:
        """Finalize the array data type by ensuring its element type is fully resolved."""
        if not isinstance(self.data_type, DataType):
            raise TypeError("finalize can only be called on instances of DataTypeBase")
