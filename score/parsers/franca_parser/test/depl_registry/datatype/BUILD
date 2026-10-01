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

filegroup(
    name = "deployment_root",
    srcs = ["test_data/datatype_properties_deployment.fdepl"],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "deployment_dependencies",
    srcs = [
        "test_data/datatype_properties.fidl",
        "test_data/score_architecture_deployment_spec.fdepl",
        "test_data/score_network_SOMEIP_deployment_spec.fdepl",
    ],
    visibility = ["//visibility:public"],
)

py_test(
    name = "deployment_property_applier_test",
    srcs = ["deployment_property_applier_test.py"],
    data = glob(["test_data/**/*"]),
    deps = ["//score/parsers/franca_parser"],
)
