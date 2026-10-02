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
load("//score/orchestrator:ecu_model.bzl", "ecu_model", "franca_inputs", "protobuf_inputs")

# Full chain example: parse Franca and Protobuf inputs into one model, then run a generator on it.
ecu_model(
    name = "example_model",
    testonly = True,
    franca = franca_inputs(
        srcs = ["//score/test_data/franca/file_graph:direct_import_root"],
        deps = ["//score/test_data/franca/file_graph:direct_import_dependency"],
    ),
    protobuf = protobuf_inputs(deps = ["//score/test_data/protobuf/pipeline:shared_proto"]),
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
