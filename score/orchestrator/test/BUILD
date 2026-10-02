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

load("@rules_python//python:defs.bzl", "py_library", "py_test")
load("//score/orchestrator:ecu_model_parse.bzl", "ecu_model_parse")

py_library(
    name = "inputs",
    testonly = True,
    srcs = ["inputs.py"],
    deps = ["@pypi//protobuf"],
)

py_test(
    name = "adapter_test",
    srcs = ["adapter_test.py"],
    main = "adapter_test.py",
    deps = [
        ":inputs",
        "//score/ecu_model",
        "//score/ecu_model:query",
        "//score/orchestrator",
    ],
)

py_test(
    name = "common_test",
    srcs = ["common_test.py"],
    main = "common_test.py",
    deps = [
        "//score/ecu_model",
        "//score/orchestrator",
    ],
)

py_test(
    name = "load_dispatch_test",
    srcs = ["load_dispatch_test.py"],
    main = "load_dispatch_test.py",
    deps = [
        ":inputs",
        "//score/ecu_model",
        "//score/ecu_model:query",
        "//score/orchestrator",
    ],
)

py_test(
    name = "run_load_dispatch_test",
    srcs = ["run_load_dispatch_test.py"],
    main = "run_load_dispatch_test.py",
    deps = [
        ":inputs",
        "//score/ecu_model",
        "//score/orchestrator:run_load_dispatch",
    ],
)

ecu_model_parse(
    name = "combined_model",
    testonly = True,
    franca_deps = [
        "//score/parsers/franca_parser/test/depl_registry/datatype:deployment_dependencies",
        "//score/parsers/franca_parser/test/parser/test_data:shared_import_dependency",
        "//score/parsers/franca_parser/test/transformer/file_graph/test_data:direct_import_dependency",
        "//score/parsers/franca_parser/test/transformer/file_graph/test_data:import_cycle_dependency",
    ],
    franca_srcs = [
        "//score/parsers/franca_parser/test/depl_registry/datatype:deployment_root",
        "//score/parsers/franca_parser/test/parser/test_data:shared_import_roots",
        "//score/parsers/franca_parser/test/transformer/file_graph/test_data:direct_import_root",
        "//score/parsers/franca_parser/test/transformer/file_graph/test_data:import_cycle_root",
    ],
    protobuf_deps = [
        "//score/parsers/protobuf_parser/test/integration/protobuf_options:custom_options_consumer_proto",
        "//score/parsers/protobuf_parser/test/integration/protobuf_pipeline:collections_and_oneof_proto",
        "//score/parsers/protobuf_parser/test/integration/protobuf_pipeline:consumer_proto",
        "//score/parsers/protobuf_parser/test/integration/protobuf_pipeline:nested_references_proto",
    ],
)

py_test(
    name = "ecu_model_parse_test",
    srcs = ["ecu_model_parse_test.py"],
    data = [":combined_model"],
    env = {"COMBINED_MODEL": "$(rootpath :combined_model)"},
    main = "ecu_model_parse_test.py",
    deps = [
        "//score/ecu_model",
        "//score/ecu_model:query",
        "//score/ecu_model/data_types",
    ],
)
