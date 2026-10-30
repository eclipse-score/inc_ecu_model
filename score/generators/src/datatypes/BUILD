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
    name = "cpp_model",
    srcs = ["cpp_model.py"],
    visibility = ["//score/generators:__subpackages__"],
)

py_library(
    name = "cpp_type_registry",
    srcs = ["cpp_type_registry.py"],
    visibility = ["//score/generators:__subpackages__"],
    deps = ["//score/ecu_model/data_types"],
)

py_library(
    name = "datatype_collector",
    srcs = ["datatype_collector.py"],
    visibility = ["//score/generators:__subpackages__"],
    deps = ["//score/ecu_model"],
)

py_library(
    name = "datatype_utils",
    srcs = [
        "datatype_utils.py",
        "primitive_type.py",
        "typedef_type.py",
    ],
    visibility = ["//score/generators:__subpackages__"],
    deps = [
        ":cpp_model",
        ":cpp_type_registry",
        "//score/ecu_model",
        "//score/ecu_model/data_types",
        "//score/generators/src/common:common_utils",
    ],
)

py_library(
    name = "header_renderer",
    srcs = ["header_renderer.py"],
    data = ["templates/datatype.h.j2"],
    visibility = ["//score/generators:__subpackages__"],
    deps = [
        ":cpp_model",
        "//score/generators/src/common:template_renderer",
    ],
)

py_library(
    name = "datatype_generator",
    srcs = ["datatype_generator.py"],
    visibility = ["//score/generators:__subpackages__"],
    deps = [
        ":cpp_model",
        ":datatype_collector",
        ":datatype_utils",
        ":header_renderer",
        "//score/ecu_model",
        "//score/generators/src/common:output_writer",
    ],
)
