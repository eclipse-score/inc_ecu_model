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

load("@rules_python//python:defs.bzl", "py_binary", "py_test")

py_binary(
    name = "generate_model_docs",
    srcs = ["generate_model_docs.py"],
    visibility = ["//visibility:public"],
    deps = [
        "//score/ecu_model",
        "//score/ecu_model:common",
        "//score/ecu_model/communication/service_interface",
        "//score/ecu_model/data_types",
    ],
)

# Guards against a stale //docs/model_reference.md being checked in.
py_test(
    name = "model_docs_test",
    srcs = ["generate_model_docs.py"],
    args = [
        "--check",
        "--output",
        "$(location //docs:model_reference.md)",
    ],
    data = ["//docs:model_reference.md"],
    main = "generate_model_docs.py",
    deps = [
        "//score/ecu_model",
        "//score/ecu_model:common",
        "//score/ecu_model/communication/service_interface",
        "//score/ecu_model/data_types",
    ],
)
