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
    name = "fidl_interface_transformer_test",
    srcs = ["fidl_interface_model_test.py"],
    data = glob(["test_data/*.fidl"]),
    main = "fidl_interface_model_test.py",
    deps = [
        "//score/parsers/franca_parser",
        "@pypi//lark",
    ],
)

py_test(
    name = "fidl_reference_resolution_test",
    srcs = ["fidl_reference_resolution_test.py"],
    deps = [
        "//score/parsers/franca_parser",
        "@pypi//lark",
    ],
)
