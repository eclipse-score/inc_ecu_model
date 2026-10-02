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

load("@protobuf//bazel:proto_library.bzl", "proto_library")

package(default_visibility = ["//visibility:public"])

proto_library(
    name = "shared_proto",
    srcs = ["shared.proto"],
    strip_import_prefix = "/score/test_data/protobuf/pipeline",
)

proto_library(
    name = "consumer_proto",
    srcs = ["consumer.proto"],
    strip_import_prefix = "/score/test_data/protobuf/pipeline",
    deps = [":shared_proto"],
)

proto_library(
    name = "nested_references_proto",
    srcs = ["nested_references.proto"],
    strip_import_prefix = "/score/test_data/protobuf/pipeline",
)

proto_library(
    name = "collections_and_oneof_proto",
    srcs = ["collections_and_oneof.proto"],
    strip_import_prefix = "/score/test_data/protobuf/pipeline",
)
