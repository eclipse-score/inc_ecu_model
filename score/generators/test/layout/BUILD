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

load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "element_layout_test",
    size = "small",
    srcs = ["element_layout_test.py"],
    deps = ["//score/generators/src/layout:element_layout"],
)

py_test(
    name = "layout_calculator_test",
    size = "small",
    srcs = ["layout_calculator_test.py"],
    deps = [
        "//score/ecu_model",
        "//score/ecu_model:common",
        "//score/ecu_model/communication",
        "//score/ecu_model/data_types",
        "//score/generators/src/layout:element_layout",
        "//score/generators/src/layout:layout_calculator",
    ],
)

py_test(
    name = "layout_generator_test",
    size = "small",
    srcs = ["layout_generator_test.py"],
    deps = [
        "//score/ecu_model",
        "//score/ecu_model:common",
        "//score/ecu_model/communication",
        "//score/ecu_model/data_types",
        "//score/generators/src:generator_runner_lib",
        "//score/generators/src/layout:element_layout",
        "//score/generators/src/layout:header_renderer",
        "//score/generators/src/layout:layout_collector",
        "//score/generators/src/layout:layout_generator",
    ],
)
