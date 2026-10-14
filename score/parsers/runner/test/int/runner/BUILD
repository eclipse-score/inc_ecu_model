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
load("//score/parsers/runner:parsers.bzl", "load_and_resolve")

package(default_visibility = ["//visibility:private"])

franca_parse(
    name = "franca_parser_demo",
    srcs = ["//score/parsers/runner/test/int/franca:franca_files"],
)

protobuf_parse(
    name = "protobuf_parser_demo",
    protobuf_deps = ["//score/parsers/runner/test/int/protobuf:protobuf_files"],
)

py_binary(
    name = "load_and_resolve_demo",
    srcs = ["//score/parsers/runner:run_load_and_resolve.py"],
    args = [
        "--output=$(BINDIR)/" + package_name() + "/load_and_resolve_demo_output.pkl",
        "--text-output=$(BINDIR)/" + package_name() + "/load_and_resolve_demo_output.txt",
        "--registry-pickle",
        "$(locations :franca_parser_demo_registry)",
        "--registry-pickle",
        "$(locations :protobuf_parser_demo_registry)",
    ],
    data = [
        ":franca_parser_demo_registry",
        ":protobuf_parser_demo_registry",
    ],
    main = "score/parsers/runner/run_load_and_resolve.py",
    deps = ["//score/parsers/runner:load_and_resolve"],
)

load_and_resolve(
    name = "load_and_resolve_build_demo",
    franca_parsers = [":franca_parser_demo"],
    protobuf_parsers = [":protobuf_parser_demo"],
    txt_out = "load_and_resolve_build_demo_output.txt",
)
