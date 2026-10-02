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
load("//score/orchestrator:ecu_model.bzl", "ecu_model", "franca_inputs", "protobuf_inputs")

py_test(
    name = "adapter_test",
    srcs = ["adapter_test.py"],
    main = "adapter_test.py",
    deps = [
        "//score/ecu_model",
        "//score/ecu_model:query",
        "//score/orchestrator",
        "//score/test_data:inputs",
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
    name = "run_parser_test",
    srcs = ["run_parser_test.py"],
    main = "run_parser_test.py",
    deps = [
        "//score/ecu_model",
        "//score/ecu_model:query",
        "//score/orchestrator:run_parser",
        "//score/test_data:inputs",
    ],
)

py_test(
    name = "merge_models_test",
    srcs = ["merge_models_test.py"],
    main = "merge_models_test.py",
    deps = [
        "//score/ecu_model",
        "//score/ecu_model:query",
        "//score/ecu_model/data_types",
        "//score/orchestrator:merge_models",
    ],
)

_FRANCA = franca_inputs(
    srcs = [
        "//score/test_data/franca/deployment:deployment_root",
        "//score/test_data/franca/file_graph:direct_import_root",
        "//score/test_data/franca/file_graph:import_cycle_root",
        "//score/test_data/franca/shared_import:shared_import_roots",
    ],
    deps = [
        "//score/test_data/franca/deployment:deployment_dependencies",
        "//score/test_data/franca/file_graph:direct_import_dependency",
        "//score/test_data/franca/file_graph:import_cycle_dependency",
        "//score/test_data/franca/shared_import:shared_import_dependency",
    ],
)

ecu_model(
    name = "combined_model",
    testonly = True,
    franca = _FRANCA,
    protobuf = protobuf_inputs(
        deps = [
            "//score/test_data/protobuf/options:custom_options_consumer_proto",
            "//score/test_data/protobuf/pipeline:collections_and_oneof_proto",
            "//score/test_data/protobuf/pipeline:consumer_proto",
            "//score/test_data/protobuf/pipeline:nested_references_proto",
        ],
    ),
)

ecu_model(
    name = "franca_only_model",
    testonly = True,
    franca = _FRANCA,
)

py_test(
    name = "ecu_model_test",
    srcs = ["ecu_model_test.py"],
    data = [
        ":combined_model",
        ":franca_only_model",
    ],
    env = {
        "COMBINED_MODEL": "$(rootpath :combined_model)",
        "FRANCA_MODEL": "$(rootpath :franca_only_model)",
    },
    main = "ecu_model_test.py",
    deps = [
        "//score/ecu_model",
        "//score/ecu_model:query",
        "//score/ecu_model/data_types",
    ],
)
