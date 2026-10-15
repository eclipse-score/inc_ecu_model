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

py_library(
    name = "preprocessor",
    srcs = [
        "batch_runner.py",
        "preprocess.py",
    ],
    visibility = ["//visibility:public"],
)

py_binary(
    name = "batch_runner",
    srcs = ["batch_runner.py"],
    visibility = ["//visibility:public"],
    deps = [":preprocessor"],
)
