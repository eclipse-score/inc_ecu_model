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
    name = "activity_test",
    size = "small",
    srcs = ["activity_test.py"],
    deps = [
        "//score/ecu_model",
        "//score/ecu_model:common",
        "//score/ecu_model/architecture",
        "//score/ecu_model/communication",
        "@pypi//pydantic",
    ],
)

py_test(
    name = "application_test",
    size = "small",
    srcs = ["application_test.py"],
    deps = [
        "//score/ecu_model",
        "//score/ecu_model:common",
        "//score/ecu_model/architecture",
        "//score/ecu_model/communication",
        "//score/ecu_model/diagnostics",
        "@pypi//pydantic",
    ],
)

py_test(
    name = "ecu_test",
    size = "small",
    srcs = ["ecu_test.py"],
    deps = [
        "//score/ecu_model",
        "//score/ecu_model/architecture",
        "//score/ecu_model/data_types",
        "//score/ecu_model/diagnostics",
        "@pypi//pydantic",
    ],
)
