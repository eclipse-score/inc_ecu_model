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
load("//score/parsers/protobuf_parser:proto_parser_example.bzl", "proto_parser_example")

package(default_visibility = ["//visibility:public"])

proto_parser_example(
    name = "options_model",
    testonly = True,
    protobuf_deps = [
        "//score/test_data/protobuf/options:custom_options_consumer_proto",
        "//score/test_data/protobuf/options:standard_options_consumer_proto",
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
