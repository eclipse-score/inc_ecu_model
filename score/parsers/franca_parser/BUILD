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

package(default_visibility = ["//visibility:public"])

py_library(
    name = "deployment_property_applier",
    srcs = [
        "deployment_property_applier.py",
    ],
    visibility = [
        "//score/parsers/franca_parser:__pkg__",
        "//score/parsers/franca_parser:__subpackages__",
    ],
    deps = [
        "//score/parsers/franca_parser/model",
    ],
)

py_library(
    name = "franca_parser",
    srcs = [
        "__init__.py",
        "parser.py",
    ],
    data = glob(["grammar/*.lark"]),
    deps = [
        "//score/parsers/franca_parser/model",
        "//score/parsers/franca_parser/transformer",
        "@pypi//lark",
    ],
)

py_binary(
    name = "franca_transformer_runner",
    testonly = True,
    srcs = ["franca_transformer_runner.py"],
    data = glob(["grammar/*.lark"]),
    main = "franca_transformer_runner.py",
    visibility = ["//visibility:private"],
    deps = [":franca_parser"],
)
