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
    name = "service_interface",
    srcs = [
        "__init__.py",
        "detail.py",
        "interface.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//score/ecu_model",
        "//score/ecu_model:common",
        "//score/ecu_model/data_types",
        "@pypi//pydantic",
    ],
)
