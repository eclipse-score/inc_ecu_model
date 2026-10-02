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
    name = "orchestrator",
    srcs = [
        "common.py",
        "parser_adapter.py",
    ],
    deps = [
        "//score/ecu_model",
        "//score/parsers/franca_parser",
        "//score/parsers/protobuf_parser",
    ],
)

py_binary(
    name = "run_parser",
    srcs = ["run_parser.py"],
    main = "run_parser.py",
    deps = [":orchestrator"],
)

py_binary(
    name = "merge_models",
    srcs = ["merge_models.py"],
    main = "merge_models.py",
    # Unpickling needs every module whose classes can occur in a partial model.
    deps = [
        "//score/ecu_model",
        "//score/ecu_model/data_types",
    ],
)
