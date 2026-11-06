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

"""Produce a raw datatype registry for generated C++ integration tests."""

import argparse
from pathlib import Path

from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.common import DataTypeSource
from score.ecu_model.data_types.composite import DataTypeField
from score.ecu_model.data_types.enum import EnumDataType, EnumValue
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.data_types.union import UnionDataType
from score.ecu_model.model import ModelRegistry


def main() -> None:
    """Write aliases, enums, arrays, inherited structs and unions with shared dependencies."""
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument("--output", type=Path, required=True)
    arguments = argument_parser.parse_args()
    aliases = {}
    for name, primitive in (
        ("Bool", PrimitiveDataType.BOOL),
        ("Float", PrimitiveDataType.FLOAT),
        ("Double", PrimitiveDataType.DOUBLE),
        ("Text", PrimitiveDataType.STRING),
        ("Int8", PrimitiveDataType.INT8),
        ("Int16", PrimitiveDataType.INT16),
        ("Int32", PrimitiveDataType.INT32),
        ("Int64", PrimitiveDataType.INT64),
        ("UInt8", PrimitiveDataType.UINT8),
        ("UInt16", PrimitiveDataType.UINT16),
        ("UInt32", PrimitiveDataType.UINT32),
        ("UInt64", PrimitiveDataType.UINT64),
    ):
        aliases[name] = TypedefDataType(
            name=name,
            namespace="example.Types",
            source_kind=DataTypeSource.FRANCA,
            data_type=primitive,
        )
    count = TypedefDataType(
        name="Count",
        namespace="example.Types",
        source_kind=DataTypeSource.FRANCA,
        data_type=aliases["UInt16"],
    )
    TypedefDataType(
        name="PublicCount",
        namespace="example.Types",
        source_kind=DataTypeSource.FRANCA,
        data_type=count,
    )
    enums = {}
    for size in (8, 16, 32, 64):
        for signed in (False, True):
            name = f"{'Int' if signed else 'UInt'}{size}Mode"
            enumeration = EnumDataType(
                name=name,
                namespace="example.Types",
                source_kind=DataTypeSource.FRANCA,
                size=size,
                signed=signed,
                values=(EnumValue(name="Minimum", value=-1 if signed else 0), EnumValue(name="Maximum", value=1)),
            )
            enums[name] = enumeration
            if size == 8 and signed:
                TypedefDataType(
                    name="PublicMode",
                    namespace="example.Types",
                    source_kind=DataTypeSource.FRANCA,
                    data_type=enumeration,
                )
    version = StructDataType(
        name="Version",
        namespace="example.Shared",
        source_kind=DataTypeSource.FRANCA,
        fields=[
            DataTypeField(name="major", data_type=PrimitiveDataType.UINT8),
            DataTypeField(name="minor", data_type=PrimitiveDataType.UINT8),
        ],
    )
    state = StructDataType(
        name="State",
        namespace="example.Types",
        source_kind=DataTypeSource.FRANCA,
        fields=[
            DataTypeField(name="enabled", data_type=PrimitiveDataType.BOOL),
            DataTypeField(name="text", data_type=PrimitiveDataType.STRING),
            DataTypeField(name="count", data_type=count),
            DataTypeField(name="mode", data_type=enums["Int8Mode"]),
            DataTypeField(name="version", data_type=version),
        ],
    )
    TypedefDataType(
        name="PublicState",
        namespace="example.Types",
        source_kind=DataTypeSource.FRANCA,
        data_type=state,
    )
    extended_state = StructDataType(
        name="ExtendedState",
        namespace="example.Derived",
        source_kind=DataTypeSource.FRANCA,
        extends=state,
        fields=[DataTypeField(name="sequence", data_type=PrimitiveDataType.UINT32)],
    )
    StructDataType(
        name="CurrentState",
        namespace="example.Types",
        source_kind=DataTypeSource.FRANCA,
        extends=extended_state,
    )
    choice = UnionDataType(
        name="Choice",
        namespace="example.Types",
        source_kind=DataTypeSource.FRANCA,
        fields=[
            DataTypeField(name="count", data_type=count),
            DataTypeField(name="raw", data_type=aliases["UInt16"]),
            DataTypeField(name="mode", data_type=enums["Int8Mode"]),
            DataTypeField(name="state", data_type=state),
            DataTypeField(name="text", data_type=PrimitiveDataType.STRING),
        ],
    )
    TypedefDataType(
        name="PublicChoice",
        namespace="example.Types",
        source_kind=DataTypeSource.FRANCA,
        data_type=choice,
    )
    payload = UnionDataType(
        name="Payload",
        namespace="example.Shared",
        source_kind=DataTypeSource.FRANCA,
        fields=[
            DataTypeField(name="flag", data_type=PrimitiveDataType.BOOL),
            DataTypeField(name="choice", data_type=choice),
        ],
    )
    extended_choice = UnionDataType(
        name="ExtendedChoice",
        namespace="example.Derived",
        source_kind=DataTypeSource.FRANCA,
        extends=choice,
        fields=[DataTypeField(name="number", data_type=PrimitiveDataType.DOUBLE)],
    )
    current_choice = UnionDataType(
        name="CurrentChoice",
        namespace="example.Types",
        source_kind=DataTypeSource.FRANCA,
        extends=extended_choice,
        fields=[DataTypeField(name="flag", data_type=PrimitiveDataType.BOOL)],
    )
    inherited_choice = UnionDataType(
        name="InheritedChoice",
        namespace="example.Shared",
        source_kind=DataTypeSource.FRANCA,
        extends=current_choice,
    )
    TypedefDataType(
        name="PublicInheritedChoice",
        namespace="example.Types",
        source_kind=DataTypeSource.FRANCA,
        data_type=inherited_choice,
    )
    StructDataType(
        name="Packet",
        namespace="example.Types",
        source_kind=DataTypeSource.FRANCA,
        fields=[
            DataTypeField(name="payload", data_type=payload),
            DataTypeField(name="inherited", data_type=inherited_choice),
        ],
    )
    row = ArrayDataType(
        name="Row",
        namespace="example.Shared",
        source_kind=DataTypeSource.FRANCA,
        data_type=PrimitiveDataType.UINT16,
        deployment_properties={"SomeIpArrayMinLength": 7, "SomeIpArrayMaxLength": 7},
    )
    TypedefDataType(
        name="PublicRow",
        namespace="example.Types",
        source_kind=DataTypeSource.FRANCA,
        data_type=row,
    )
    samples = ArrayDataType(
        name="Samples",
        namespace="example.Types",
        source_kind=DataTypeSource.FRANCA,
        data_type=PrimitiveDataType.UINT16,
        deployment_properties={"SomeIpArrayMinLength": 0, "SomeIpArrayMaxLength": 7},
    )
    ArrayDataType(
        name="ZeroBounds",
        namespace="example.Types",
        source_kind=DataTypeSource.FRANCA,
        data_type=PrimitiveDataType.BOOL,
        dimension_min=0,
        dimension_max=0,
    )
    states = ArrayDataType(
        name="States",
        namespace="example.Types",
        source_kind=DataTypeSource.FRANCA,
        data_type=state,
        dimension_min=3,
        dimension_max=3,
    )
    inline = ArrayDataType(
        is_inline=True,
        source_kind=DataTypeSource.FRANCA,
        data_type=PrimitiveDataType.UINT16,
    )
    rows = ArrayDataType(is_inline=True, source_kind=DataTypeSource.FRANCA, data_type=row)
    StructDataType(
        name="Grid",
        namespace="example.Types",
        source_kind=DataTypeSource.FRANCA,
        fields=[
            DataTypeField(
                name="rows",
                data_type=rows,
                deployment_properties={"SomeIpArrayMinLength": 5, "SomeIpArrayMaxLength": 5},
            ),
            DataTypeField(
                name="row", data_type=row, deployment_properties={"SomeIpArrayMinLength": 2, "SomeIpArrayMaxLength": 2}
            ),
            DataTypeField(name="samples", data_type=samples),
            DataTypeField(
                name="fixed",
                data_type=inline,
                deployment_properties={"SomeIpArrayMinLength": 3, "SomeIpArrayMaxLength": 3},
            ),
        ],
    )
    UnionDataType(
        name="ArrayChoice",
        namespace="example.Types",
        source_kind=DataTypeSource.FRANCA,
        fields=[
            DataTypeField(name="named", data_type=samples),
            DataTypeField(
                name="dynamic",
                data_type=inline,
                deployment_properties={"SomeIpArrayMinLength": 3, "SomeIpArrayMaxLength": 9},
            ),
            DataTypeField(
                name="fixed",
                data_type=inline,
                deployment_properties={"SomeIpArrayMinLength": 3, "SomeIpArrayMaxLength": 3},
            ),
            DataTypeField(name="states", data_type=states),
        ],
    )
    arguments.output.write_bytes(ModelRegistry.serialize())


if __name__ == "__main__":
    main()
