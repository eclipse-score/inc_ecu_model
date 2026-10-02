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
    name = "model",
    srcs = [
        "__init__.py",
        "fdepl/__init__.py",
        "fdepl/definition.py",
        "fdepl/fdepl_file.py",
        "fdepl/specification.py",
        "fdepl/type_collection_deployment.py",
        "fidl/__init__.py",
        "fidl/fidl_file.py",
        "fidl/type_collection.py",
        "franca_file.py",
        "parsed_file.py",
    ],
    visibility = [
        "//score/parsers/franca_parser:__pkg__",
        "//score/parsers/franca_parser:__subpackages__",
    ],
    deps = [
        "//score/ecu_model/data_types",
    ],
)
