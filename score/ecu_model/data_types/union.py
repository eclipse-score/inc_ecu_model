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

from pydantic import Field, field_validator

from score.ecu_model.data_types.common import DataTypeKind
from score.ecu_model.data_types.composite import CompositeDataType, DataTypeField


class UnionDataType(CompositeDataType):
    """A declared union data type whose fields are mutually exclusive,  e.g. a Franca union or a protobuf oneof."""

    kind: Literal[DataTypeKind.UNION] = Field(default=DataTypeKind.UNION, frozen=True)

    @field_validator("fields")
    @classmethod
    def _reject_optional_fields(cls, fields: tuple[DataTypeField, ...]) -> tuple[DataTypeField, ...]:
        """Reject optional fields, as union fields are mutually exclusive and therefore optional by definition."""
        for field in fields:
            if field.optional:
                raise ValueError("union fields must not be declared optional")
        return fields
