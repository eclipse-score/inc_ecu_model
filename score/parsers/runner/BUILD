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

load("@rules_python//python:defs.bzl", "py_binary", "py_library")
load(":parsers.bzl", "load_dispatch_parse")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "common",
    srcs = ["common.py"],
)

py_library(
    name = "parsers",
    srcs = ["load_dispatch.py"],
    deps = [
        ":common",
        "//score/parsers/franca_parser:franca_parser",
        "//score/parsers/protobuf_parser:protobuf_parser",
    ],
)

py_binary(
    name = "run_load_dispatch",
    srcs = ["run_load_dispatch.py"],
    main = "run_load_dispatch.py",
    deps = [
        ":parsers",
        "@pypi//pydantic",
        "@rules_python//python/runfiles",
    ],
)

py_binary(
    name = "load_dispatch_demo",
    srcs = ["run_load_dispatch.py"],
    args = [
        "--output=$(BINDIR)/" + package_name() + "/load_dispatch_demo_output.pkl",
        "--text-output=$(BINDIR)/" + package_name() + "/load_dispatch_demo_output.txt",
        "--franca-files",
        "$(locations //score/parsers/runner/test/int/franca:franca_files)",
        "--protobuf-files",
        "$(locations //score/parsers/runner/test/int/protobuf:protobuf_files)",
    ],
    data = [
        "//score/parsers/runner/test/int/franca:franca_files",
        "//score/parsers/runner/test/int/protobuf:protobuf_files",
    ],
    main = "run_load_dispatch.py",
    deps = [
        ":parsers",
        "@pypi//pydantic",
        "@rules_python//python/runfiles",
    ],
)

load_dispatch_parse(
    name = "load_dispatch_parse_demo",
    franca_srcs = ["//score/parsers/runner/test/int/franca:franca_files"],
    protobuf_deps = ["//score/parsers/runner/test/int/protobuf:protobuf_files"],
)
