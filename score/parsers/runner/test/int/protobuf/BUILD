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

load("//score/parsers/protobuf_parser:proto_parser_example.bzl", "proto_descriptor_sets")

package(default_visibility = ["//visibility:public"])

proto_descriptor_sets(
    name = "protobuf_files",
    protobuf_deps = [
        "//score/parsers/protobuf_parser/test/integration/protobuf_pipeline:consumer_proto",
        "//score/parsers/protobuf_parser/test/integration/protobuf_pipeline:nested_references_proto",
        "//score/parsers/protobuf_parser/test/integration/protobuf_pipeline:collections_and_oneof_proto",
    ],
)
