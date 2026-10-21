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

load("@rules_python//python:defs.bzl", "py_binary")
load("//score/parsers/franca_parser:franca_parser.bzl", "franca_parse")
load("//score/parsers/protobuf_parser:proto_parser.bzl", "protobuf_parse")
load("//score/parsers/runner:parsers.bzl", "load_and_merge")

package(default_visibility = ["//visibility:private"])

franca_parse(
    name = "franca_parser_demo",
    srcs = [
        "interface.fidl",
        "//score/parsers/franca_parser/test/transformer/file_graph/test_data:direct_import_root",
    ],
    deps = ["//score/parsers/franca_parser/test/transformer/file_graph/test_data:direct_import_dependency"],
)

protobuf_parse(
    name = "protobuf_parser_demo",
    protobuf_deps = [
        "//score/parsers/protobuf_parser/test/integration/protobuf_pipeline:consumer_proto",
        "//score/parsers/protobuf_parser/test/integration/protobuf_pipeline:nested_references_proto",
        "//score/parsers/protobuf_parser/test/integration/protobuf_pipeline:collections_and_oneof_proto",
    ],
)

py_binary(
    name = "load_and_merge_demo",
    srcs = ["//score/parsers/runner:run_load_and_merge.py"],
    args = [
        "--output=$(BINDIR)/" + package_name() + "/load_and_merge_demo_output.pkl",
        "--text-output=$(BINDIR)/" + package_name() + "/load_and_merge_demo_output.txt",
        "--registry-pickle",
        "$(locations :franca_parser_demo)",
        "--registry-pickle",
        "$(locations :protobuf_parser_demo)",
    ],
    data = [
        ":franca_parser_demo",
        ":protobuf_parser_demo",
    ],
    main = "score/parsers/runner/run_load_and_merge.py",
    deps = ["//score/parsers/runner:load_and_merge"],
)

load_and_merge(
    name = "load_and_merge_build_demo",
    out = "load_and_merge_build_demo_output.pkl",
    parsers = [
        ":franca_parser_demo",
        ":protobuf_parser_demo",
    ],
    txt_out = "load_and_merge_build_demo_output.txt",
)
