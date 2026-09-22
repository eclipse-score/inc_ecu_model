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
    name = "communication",
    srcs = [
        "__init__.py",
        "detail/__init__.py",
        "detail/base_port.py",
        "detail/deployment_binding.py",
        "detail/message_port.py",
        "detail/service_port.py",
        "message_channel.py",
        "message_port.py",
        "service_interface.py",
        "service_port.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//score/ecu_model",
        "//score/ecu_model:common",
        "//score/ecu_model/data_types",
        "@pypi//pydantic",
    ],
)
