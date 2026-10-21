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

filegroup(
    name = "interface_samples",
    srcs = glob(["test_data/*.fidl"]),
    visibility = ["//score/parsers/franca_parser:__subpackages__"],
)

py_test(
    name = "interface_grammar_test",
    srcs = ["interface_grammar_test.py"],
    data = [
        ":interface_samples",
        "//score/parsers/franca_parser:fidl_grammar_files",
    ],
    deps = ["@pypi//lark"],
)
