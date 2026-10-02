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
    name = "franca_file_graph_transformer_test",
    srcs = ["franca_file_graph_transformer_test.py"],
    data = ["//score/test_data/franca/file_graph:fidl_files"],
    deps = ["//score/parsers/franca_parser"],
)

franca_transformer(
    name = "franca_transformer_fixture",
    srcs = ["//score/test_data/franca/file_graph:direct_import_root"],
    deps = ["//score/test_data/franca/file_graph:direct_import_dependency"],
)
