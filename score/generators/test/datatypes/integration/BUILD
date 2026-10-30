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

load("@rules_cc//cc:defs.bzl", "cc_test")
load("@rules_python//python:defs.bzl", "py_binary")
load("//score/generators:score_ecu_model.bzl", "cc_score_ecu_model_library", "score_ecu_model_artifacts")
load("//score/parsers/runner:parsers.bzl", "load_and_merge")

py_binary(
    name = "create_test_model",
    testonly = True,
    srcs = ["create_test_model.py"],
    deps = [
        "//score/ecu_model",
        "//score/ecu_model/data_types",
    ],
)

genrule(
    name = "test_model_registry",
    testonly = True,
    outs = ["test_model_registry.pkl"],
    cmd = "$(location :create_test_model) --output $@",
    tools = [":create_test_model"],
)

load_and_merge(
    name = "test_model",
    testonly = True,
    out = "test_model.pkl",
    parsers = [":test_model_registry"],
)

score_ecu_model_artifacts(
    name = "test_artifacts",
    testonly = True,
    model = ":test_model",
)

cc_score_ecu_model_library(
    name = "test_headers",
    testonly = True,
    artifacts = ":test_artifacts",
)

cc_test(
    name = "generated_header_test",
    size = "small",
    srcs = ["generated_header_test.cpp"],
    copts = ["-std=c++17"],
    deps = [":test_headers"],
)
