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

load("@rules_python//python:defs.bzl", "py_binary", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "protobuf_parser",
    srcs = [
        "api.py",
        "common.py",
        "option_decoder.py",
        "resolver.py",
        "transformer.py",
    ],
    deps = [
        "//score/ecu_model/data_types",
        "@pypi//protobuf",
    ],
)

py_binary(
    name = "proto_parser_runner",
    testonly = True,
    srcs = ["proto_parser_runner.py"],
    main = "proto_parser_runner.py",
    deps = [":protobuf_parser"],
)
