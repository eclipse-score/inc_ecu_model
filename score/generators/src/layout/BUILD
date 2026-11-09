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

load("@rules_python//python:defs.bzl", "py_library")

py_library(
    name = "element_layout",
    srcs = ["element_layout.py"],
    visibility = ["//score/generators:__subpackages__"],
)

py_library(
    name = "layout_calculator",
    srcs = ["layout_calculator.py"],
    visibility = ["//score/generators:__subpackages__"],
    deps = [
        ":element_layout",
        "//score/ecu_model/communication",
        "//score/ecu_model/data_types",
        "//score/generators/src/common:array_bounds",
    ],
)

py_library(
    name = "layout_collector",
    srcs = ["layout_collector.py"],
    visibility = ["//score/generators:__subpackages__"],
    deps = [
        "//score/ecu_model",
        "//score/ecu_model/communication",
    ],
)

py_library(
    name = "header_renderer",
    srcs = ["header_renderer.py"],
    data = ["templates/layout.h.j2"],
    visibility = ["//score/generators:__subpackages__"],
    deps = [
        ":element_layout",
        "//score/generators/src/common:common_utils",
        "//score/generators/src/common:template_renderer",
    ],
)

py_library(
    name = "layout_generator",
    srcs = ["layout_generator.py"],
    visibility = ["//score/generators:__subpackages__"],
    deps = [
        ":element_layout",
        ":header_renderer",
        ":layout_calculator",
        ":layout_collector",
        ":layout_json_renderer",
        "//score/ecu_model",
        "//score/generators/src/common:output_writer",
    ],
)

py_library(
    name = "layout_json_renderer",
    srcs = ["layout_json_renderer.py"],
    visibility = ["//score/generators:__subpackages__"],
    deps = [
        ":element_layout",
        "//score/ecu_model/communication",
    ],
)
