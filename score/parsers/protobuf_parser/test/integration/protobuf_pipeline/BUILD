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

load("@rules_proto//proto:defs.bzl", "proto_library")
load("@rules_python//python:defs.bzl", "py_test")
load("//score/parsers/protobuf_parser:proto_parser.bzl", "proto_parser")

package(default_visibility = ["//visibility:public"])

proto_library(
    name = "shared_proto",
    srcs = ["test_data/shared.proto"],
    strip_import_prefix = "test_data",
)

proto_library(
    name = "consumer_proto",
    srcs = ["test_data/consumer.proto"],
    strip_import_prefix = "test_data",
    deps = [":shared_proto"],
)

proto_library(
    name = "nested_references_proto",
    srcs = ["test_data/nested_references.proto"],
    strip_import_prefix = "test_data",
)

proto_library(
    name = "collections_and_oneof_proto",
    srcs = ["test_data/collections_and_oneof.proto"],
    strip_import_prefix = "test_data",
)

proto_parser(
    name = "pipeline_model",
    protobuf_deps = [
        ":consumer_proto",
        ":nested_references_proto",
        ":collections_and_oneof_proto",
    ],
)

py_test(
    name = "protobuf_pipeline_integration_test",
    srcs = ["protobuf_pipeline_integration_test.py"],
    data = [":pipeline_model"],
    main = "protobuf_pipeline_integration_test.py",
    deps = [
        "//score/ecu_model",
        "//score/parsers/protobuf_parser",
    ],
)
