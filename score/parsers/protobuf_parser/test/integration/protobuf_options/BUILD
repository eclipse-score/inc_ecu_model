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
load("//score/parsers/protobuf_parser:proto_parser.bzl", "protobuf_parse")

package(default_visibility = ["//visibility:public"])

proto_library(
    name = "custom_options_proto",
    srcs = ["test_data/custom_options.proto"],
    strip_import_prefix = "test_data",
    deps = ["@com_google_protobuf//:descriptor_proto"],
)

proto_library(
    name = "custom_options_consumer_proto",
    srcs = ["test_data/custom_options_consumer.proto"],
    strip_import_prefix = "test_data",
    deps = [":custom_options_proto"],
)

proto_library(
    name = "standard_options_consumer_proto",
    srcs = ["test_data/standard_options_consumer.proto"],
    strip_import_prefix = "test_data",
)

protobuf_parse(
    name = "options_model",
    protobuf_deps = [
        ":custom_options_consumer_proto",
        ":standard_options_consumer_proto",
    ],
)

py_test(
    name = "protobuf_options_integration_test",
    srcs = ["protobuf_options_integration_test.py"],
    data = [":options_model"],
    main = "protobuf_options_integration_test.py",
    deps = [
        "//score/ecu_model",
        "//score/parsers/protobuf_parser",
    ],
)
