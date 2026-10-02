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
    name = "ecu_model",
    srcs = ["model.py"],
    visibility = ["//visibility:public"],
    deps = [
        "@pypi//pydantic",
    ],
)

py_library(
    name = "query",
    srcs = ["query.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":ecu_model",
        "//score/ecu_model/data_types",
    ],
)

py_library(
    name = "common",
    srcs = [
        "common/__init__.py",
        "common/asil_level.py",
        "common/version.py",
    ],
    visibility = ["//visibility:public"],
    deps = ["@pypi//pydantic"],
)
