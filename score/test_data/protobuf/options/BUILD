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
    name = "custom_options_proto",
    srcs = ["custom_options.proto"],
    strip_import_prefix = "/score/test_data/protobuf/options",
    deps = ["@com_google_protobuf//:descriptor_proto"],
)

proto_library(
    name = "custom_options_consumer_proto",
    srcs = ["custom_options_consumer.proto"],
    strip_import_prefix = "/score/test_data/protobuf/options",
    deps = [":custom_options_proto"],
)

proto_library(
    name = "standard_options_consumer_proto",
    srcs = ["standard_options_consumer.proto"],
    strip_import_prefix = "/score/test_data/protobuf/options",
)
