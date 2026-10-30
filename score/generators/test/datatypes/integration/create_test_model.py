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

"""Produce a raw registry for the primitive/typedef build-time integration test."""

import argparse
from pathlib import Path

from score.ecu_model.data_types.common import DataTypeSource
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.model import ModelRegistry


def main() -> None:
    """Write a datatype-only registry with primitive aliases and a typedef dependency chain."""
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
    arguments.output.write_bytes(ModelRegistry.serialize())


if __name__ == "__main__":
    main()
