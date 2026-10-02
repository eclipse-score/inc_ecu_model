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

load("@rules_python//python:defs.bzl", "py_library")

py_library(
    name = "transformer",
    srcs = [
        "__init__.py",
        "base_transformer.py",
        "fdepl_transformer.py",
        "fidl_transformer.py",
        "file_graph_transformer.py",
        "import_transformer.py",
        "resolver/__init__.py",
        "resolver/fdepl_resolver.py",
        "resolver/fidl_datatype_resolver.py",
        "resolver/utils_resolver.py",
    ],
    visibility = [
        "//score/orchestrator:__pkg__",
        "//score/parsers/franca_parser:__pkg__",
        "//score/parsers/franca_parser:__subpackages__",
    ],
    deps = [
        "//score/ecu_model/data_types",
        "//score/parsers/franca_parser:deployment_property_applier",
        "//score/parsers/franca_parser/model",
        "@pypi//lark",
    ],
)
