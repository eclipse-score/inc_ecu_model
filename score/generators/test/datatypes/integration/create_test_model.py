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

"""Produce a raw datatype registry for primitive, typedef, enum and struct integration tests."""

import argparse
from pathlib import Path

from score.ecu_model.data_types.common import DataTypeSource
from score.ecu_model.data_types.composite import DataTypeField
from score.ecu_model.data_types.enum import EnumDataType, EnumValue
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.model import ModelRegistry


def main() -> None:
    """Write aliases, enums and inherited structs with shared named dependencies."""
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
    arguments.output.write_bytes(ModelRegistry.serialize())


if __name__ == "__main__":
    main()
