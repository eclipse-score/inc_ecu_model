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

load("@protobuf//bazel:proto_library.bzl", "proto_library")
load("@rules_python//python:defs.bzl", "py_test")
load("//score/parsers/protobuf_parser:proto_parser_example.bzl", "proto_parser_example")

package(default_visibility = ["//visibility:public"])

proto_library(
    name = "public_transitive_dependency_proto",
    srcs = ["test_data/public_transitive/transitive_dependency.proto"],
    strip_import_prefix = "test_data/public_transitive",
)

proto_library(
    name = "public_direct_dependency_proto",
    srcs = ["test_data/public_transitive/direct_dependency.proto"],
    strip_import_prefix = "test_data/public_transitive",
    exports = [":public_transitive_dependency_proto"],
    deps = [":public_transitive_dependency_proto"],
)

proto_library(
    name = "public_consumer_proto",
    srcs = ["test_data/public_transitive/consumer.proto"],
    strip_import_prefix = "test_data/public_transitive",
    deps = [":public_direct_dependency_proto"],
)

proto_parser_example(
    name = "public_import_model",
    testonly = True,
    protobuf_deps = [":public_consumer_proto"],
)

py_test(
    name = "protobuf_import_visibility_integration_test",
    srcs = ["protobuf_import_visibility_integration_test.py"],
    data = [":public_import_model"],
    main = "protobuf_import_visibility_integration_test.py",
    deps = [
        "//score/parsers/protobuf_parser",
    ],
)
