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
    name = "detail_test",
    size = "small",
    srcs = ["detail_test.py"],
    deps = [
        "//score/ecu_model",
        "//score/ecu_model/communication",
        "@pypi//pydantic",
    ],
)

py_test(
    name = "service_interface_test",
    size = "small",
    srcs = ["service_interface_test.py"],
    deps = [
        "//score/ecu_model",
        "//score/ecu_model:common",
        "//score/ecu_model/communication",
        "//score/ecu_model/data_types",
        "@pypi//pydantic",
    ],
)

py_test(
    name = "message_channel_test",
    size = "small",
    srcs = ["message_channel_test.py"],
    deps = [
        "//score/ecu_model",
        "//score/ecu_model/communication",
        "//score/ecu_model/data_types",
        "@pypi//pydantic",
    ],
)

py_test(
    name = "service_port_test",
    size = "small",
    srcs = ["service_port_test.py"],
    deps = [
        "//score/ecu_model",
        "//score/ecu_model:common",
        "//score/ecu_model/communication",
        "@pypi//pydantic",
    ],
)

py_test(
    name = "message_port_test",
    size = "small",
    srcs = ["message_port_test.py"],
    deps = [
        "//score/ecu_model",
        "//score/ecu_model/communication",
        "//score/ecu_model/data_types",
    ],
)
