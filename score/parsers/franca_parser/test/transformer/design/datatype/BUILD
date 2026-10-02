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
load("//score/parsers/franca_parser:franca_transformer.bzl", "franca_transformer")

py_test(
    name = "fidl_datatype_resolver_test",
    srcs = ["fidl_datatype_resolver_test.py"],
    deps = ["//score/parsers/franca_parser"],
)

py_test(
    name = "utils_resolver_test",
    srcs = ["utils_resolver_test.py"],
    deps = ["//score/parsers/franca_parser"],
)

py_test(
    name = "fidl_datatype_transformer_test",
    srcs = ["fidl_datatype_transformer_test.py"],
    data = glob(["test_data/**/*.fidl"]),
    deps = ["//score/parsers/franca_parser"],
)

franca_transformer(
    name = "fidl_datatype_pickle",
    testonly = True,
    srcs = ["test_data/reference_resolution/file_only_root.fidl"],
    deps = [
        "test_data/reference_resolution/anonymous_types.fidl",
        "test_data/reference_resolution/shared_types.fidl",
    ],
)
