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

"""Write minimal parser input files for the orchestrator tests."""

from __future__ import annotations

from pathlib import Path

from google.protobuf import descriptor_pb2


def write_fidl(directory: Path, package: str, type_collection: str, struct: str) -> Path:
    """Write a FIDL file declaring one struct, whose FQN is package.type_collection.struct."""
    path = directory / f"{struct}.fidl"
    path.write_text(
        f"package {package}\n"
        f"typeCollection {type_collection} {{\n"
        f"    struct {struct} {{\n"
        "        UInt32 value\n"
        "    }\n"
        "}\n"
    )
    return path


def write_descriptor_set(directory: Path, package: str, message: str) -> Path:
    """Write a descriptor set declaring one message, whose FQN is package.message."""
    file_descriptor = descriptor_pb2.FileDescriptorProto(name=f"{message}.proto", package=package, syntax="proto3")
    file_descriptor.message_type.add(name=message)
    descriptor_set = descriptor_pb2.FileDescriptorSet()
    descriptor_set.file.add().CopyFrom(file_descriptor)
    path = directory / f"{message}.pb"
    path.write_bytes(descriptor_set.SerializeToString())
    return path
