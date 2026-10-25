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
    name = "common_utils",
    srcs = ["common_utils.py"],
    visibility = ["//score/generators:__subpackages__"],
)

py_library(
    name = "template_renderer",
    srcs = ["template_renderer.py"],
    visibility = ["//score/generators:__subpackages__"],
    deps = ["@pypi//jinja2"],
)

py_library(
    name = "output_writer",
    srcs = ["output_writer.py"],
    visibility = ["//score/generators:__subpackages__"],
)
