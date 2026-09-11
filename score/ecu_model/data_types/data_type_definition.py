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

from enum import Enum
from typing import Annotated, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

from score.ecu_model.common.common_name_types import Identifier, QualifiedName
from score.ecu_model.common.bazel_target_validator import (
    validate_bazel_target_text,
)
from score.ecu_model.common.file_system_path_validator import (
    validate_path_text,
)


class DataTypeKind(str, Enum):
    """Discriminator values for concrete DataType definition models."""

    PRIMITIVE = "primitive"
    ENUM = "enum"
    STRUCT = "struct"
    UNION = "union"
    ARRAY = "array"
    MAP = "map"
    TYPEDEF = "typedef"
    EXTERNAL = "external"


class PrimitiveDataTypeKind(str, Enum):
    """Canonical primitive data types supported by generator inputs."""

    STRING = "string"
    BYTES = "bytes"
    BOOL = "bool"
    DOUBLE = "double"
    FLOAT = "float"
    UINT8 = "uint8"
    UINT16 = "uint16"
    UINT32 = "uint32"
    UINT64 = "uint64"
    INT8 = "int8"
    INT16 = "int16"
    INT32 = "int32"
    INT64 = "int64"

    def __str__(self) -> str:
        """Return the canonical primitive data type name."""
        return self.value


class DataTypeModel(BaseModel):
    """Shared metadata for concrete data type definitions."""

    kind: DataTypeKind = Field(
        description="Discriminator identifying the concrete data type definition kind",
    )
    name: Identifier = Field(
        description="Name of the data type definition in its source namespace",
    )
    namespace: QualifiedName | None = Field(
        default=None,
        description="Optional namespace/module/package in which this data type is declared",
    )
    source_kind: str | None = Field(
        default=None,
        description="Origin of the data type definition, e.g. franca, protobuf, builtin",
    )
    source_uri: str | None = Field(
        default=None,
        description="Optional source file URI/path where this data type definition was imported from",
    )
    description: str = Field(
        default="",
        description="Human-readable description of the data type definition",
    )
    deployment_properties: dict[str, object] = Field(
        default_factory=dict,
        description="Deployment properties aggregated from all communication bindings using this data type",
    )

    @property
    def fully_qualified_name(self) -> QualifiedName:
        """Return the data type name prefixed with its namespace."""
        names = self.namespace.names if self.namespace is not None else []
        return QualifiedName(names=[*names, self.name])

    @field_validator("source_uri")
    @classmethod
    def _validate_source_uri_is_filesystem_path(cls, value: str | None) -> str | None:
        """Validate that `source_uri` is a non-empty filesystem path string."""
        return validate_path_text(value, "source_uri")


class PrimitiveDataType(DataTypeModel):
    """Definition of a primitive builtin data type from the compiler library."""

    kind: Literal[DataTypeKind.PRIMITIVE] = DataTypeKind.PRIMITIVE
    primitive: PrimitiveDataTypeKind = Field(
        description="Canonical primitive data type used by generators",
    )


class ExternalDataType(DataTypeModel):
    """Definition of a type provided by an existing C++ header without modeled internals."""

    kind: Literal[DataTypeKind.EXTERNAL] = DataTypeKind.EXTERNAL
    header: str = Field(
        description="Header include path or explicitly quoted/bracketed include.",
    )
    bazel_target: str | None = Field(
        default=None,
        description="Optional Bazel dependency target required for the payload type.",
    )

    @field_validator("bazel_target")
    @classmethod
    def _validate_bazel_target(cls, value: str | None) -> str | None:
        """Validate the optional Bazel target that supplies the header."""
        return validate_bazel_target_text(value, "bazel_target")


class EnumDataType(DataTypeModel):
    """Definition of an enum data type with named literals."""

    kind: Literal[DataTypeKind.ENUM] = DataTypeKind.ENUM
    extends: QualifiedName | EnumDataType | None = None
    underlying_type: PrimitiveDataType = Field(
        default_factory=lambda: PrimitiveDataType(
            name=Identifier("uint32_t"),
            namespace=QualifiedName(names=[Identifier("std")]),
            primitive=PrimitiveDataTypeKind.UINT32,
        ),
        description="Underlying primitive type used for enum storage",
    )
    values: list[Annotated["EnumValue", Field()]] = Field(default_factory=list)


class EnumValue(BaseModel):
    """Definition of a single enum literal with optional numeric value."""

    name: Identifier = Field(
        description="Name of the enum literal",
    )
    value: int | None = Field(
        default=None,
        description="Optional constant value assigned to the enum literal",
    )

    @field_validator("value", mode="before")
    @classmethod
    def _reject_boolean_enum_values(cls, value: int | bool | None) -> int | None:
        """Reject booleans so True/False are not silently accepted as 1/0."""
        if isinstance(value, bool):
            raise ValueError("enum value must be an integer, not boolean")
        return value


class DataTypeField(BaseModel):
    """Definition of a single field in a struct or union data type definition."""

    name: Identifier = Field(
        description="Field name as declared in the source data type definition",
    )
    data_type: QualifiedName | DataTypeDefinition = Field(
        description="Field data type definition; may temporarily be an unresolved reference during model resolution",
    )
    description: str = Field(
        default="",
        description="Human-readable description of the field",
    )
    field_number: int | None = Field(
        default=None,
        description="Wire tag / field number (e.g. protobuf field number), if defined by the source IDL",
    )
    optional: bool = Field(
        default=False,
        description="Whether the field is optional (proto2 optional, Franca optional field)",
    )
    default: str | None = Field(
        default=None,
        description="Optional default value carried over from the source IDL, serialized as string",
    )
    deployment_properties: dict[str, object] = Field(
        default_factory=dict,
        description="Deployment properties aggregated from all communication bindings using this field",
    )


class StructDataType(DataTypeModel):
    """Definition of a struct data type with named fields."""

    kind: Literal[DataTypeKind.STRUCT] = DataTypeKind.STRUCT
    extends: QualifiedName | StructDataType | None = None
    fields: list[DataTypeField] = Field(default_factory=list)


class UnionDataType(DataTypeModel):
    """Definition of a union data type with mutually exclusive variants."""

    kind: Literal[DataTypeKind.UNION] = DataTypeKind.UNION
    extends: QualifiedName | UnionDataType | None = None
    fields: list[DataTypeField] = Field(
        default_factory=list,
        description="Mutually exclusive variants (Franca union members / protobuf oneof cases)",
    )


class ArrayDataType(DataTypeModel):
    """Definition of an array data type with element type and optional dimensions."""

    kind: Literal[DataTypeKind.ARRAY] = DataTypeKind.ARRAY
    name: Identifier | None = Field(
        default=None,
        description="Name of a named array definition; absent for inline arrays",
    )
    data_type: QualifiedName | DataTypeDefinition = Field(
        description="Array element type definition; may temporarily be an unresolved reference during model resolution",
    )
    is_inline: bool = False
    dimension_min: int | None = None
    dimension_max: int | None = None

    @field_validator("dimension_min", "dimension_max")
    @classmethod
    def _validate_dimension_bound_is_non_negative(cls, value: int | None) -> int | None:
        """Validate array dimension bounds as non-negative integers when provided."""
        if value is not None and value < 0:
            raise ValueError("array dimension bounds must be non-negative")
        return value

    @model_validator(mode="after")
    def _validate_dimension_range(self) -> "ArrayDataType":
        """Validate array naming and dimension constraints."""
        if self.is_inline and self.name is not None:
            raise ValueError("inline arrays must not have a name")
        if not self.is_inline and self.name is None:
            raise ValueError("non-inline arrays require a name")
        if (
            self.dimension_min is not None
            and self.dimension_max is not None
            and self.dimension_min > self.dimension_max
        ):
            raise ValueError("dimension_min must not be greater than dimension_max")
        return self


class MapDataType(DataTypeModel):
    """Definition of a map data type with key and value types."""

    kind: Literal[DataTypeKind.MAP] = DataTypeKind.MAP
    map_from: QualifiedName | DataTypeDefinition = Field(
        description="Map key type definition; may temporarily be an unresolved reference during model resolution",
    )
    map_to: QualifiedName | DataTypeDefinition = Field(
        description="Map value type definition; may temporarily be an unresolved reference during model resolution",
    )


class TypedefDataType(DataTypeModel):
    """Definition of a typedef data type pointing to another data type."""

    kind: Literal[DataTypeKind.TYPEDEF] = DataTypeKind.TYPEDEF
    data_type: QualifiedName | DataTypeDefinition = Field(
        description="Aliased type definition; may temporarily be an unresolved reference during model resolution",
    )


DataTypeDefinition = Annotated[
    PrimitiveDataType
    | ExternalDataType
    | EnumDataType
    | StructDataType
    | UnionDataType
    | ArrayDataType
    | MapDataType
    | TypedefDataType,
    Field(discriminator="kind"),
]

EnumDataType.model_rebuild()
DataTypeField.model_rebuild()
StructDataType.model_rebuild()
UnionDataType.model_rebuild()
ArrayDataType.model_rebuild()
MapDataType.model_rebuild()
TypedefDataType.model_rebuild()
