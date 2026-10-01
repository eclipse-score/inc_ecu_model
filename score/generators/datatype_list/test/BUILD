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

load("@bazel_skylib//rules:diff_test.bzl", "diff_test")
load("//score/generators/datatype_list:datatype_list.bzl", "datatype_list")
load("//score/orchestrator:ecu_model_parse.bzl", "ecu_model_parse")

# Full chain example: parse Franca and Protobuf inputs into one model, then run a generator on it.
ecu_model_parse(
    name = "example_model",
    testonly = True,
    franca_deps = ["//score/parsers/franca_parser/test/transformer/file_graph/test_data:direct_import_dependency"],
    franca_srcs = ["//score/parsers/franca_parser/test/transformer/file_graph/test_data:direct_import_root"],
    protobuf_deps = ["//score/parsers/protobuf_parser/test/integration/protobuf_pipeline:shared_proto"],
)

datatype_list(
    name = "example_datatypes",
    testonly = True,
    model = ":example_model",
)

diff_test(
    name = "example_datatypes_test",
    file1 = ":example_datatypes",
    file2 = "expected_datatypes.txt",
)
