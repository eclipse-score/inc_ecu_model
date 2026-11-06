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

load("@rules_python//python:defs.bzl", "py_binary", "py_test")
load("//score/parsers/franca_parser:franca_parser.bzl", "franca_parse")

franca_parse(
    name = "fidl_integration_model",
    srcs = ["//score/parsers/franca_parser/test/parser/test_data:registry_integration/service.fidl"],
    deps = [
        "//score/parsers/franca_parser/test/parser/test_data:registry_integration/common.fidl",
        "//score/parsers/franca_parser/test/parser/test_data:registry_integration/events.fidl",
    ],
)

py_binary(
    name = "dump_fidl_integration_model",
    srcs = ["fidl_registry_integration_test.py"],
    main = "fidl_registry_integration_test.py",
    deps = [
        "//score/ecu_model",
        "//score/ecu_model/communication",
        "//score/ecu_model/data_types",
        "@pypi//pydantic",
    ],
)

genrule(
    name = "fidl_integration_model_json",
    srcs = [":fidl_integration_model"],
    outs = ["fidl_integration_model.json"],
    cmd = "$(location :dump_fidl_integration_model) --pickle $(location :fidl_integration_model) --json $@",
    tools = [":dump_fidl_integration_model"],
)

py_test(
    name = "fidl_registry_integration_test",
    srcs = ["fidl_registry_integration_test.py"],
    data = [
        ":fidl_integration_model",
        ":fidl_integration_model_json",
    ],
    deps = [
        "//score/ecu_model",
        "//score/ecu_model/communication",
        "//score/ecu_model/data_types",
        "@pypi//pydantic",
    ],
)

py_test(
    name = "interface_model_test",
    srcs = ["interface_model_test.py"],
    deps = [
        "//score/parsers/franca_parser",
        "//score/parsers/franca_parser:franca_model_parser_runner",
        "@pypi//lark",
    ],
)

py_test(
    name = "franca_parser_test",
    srcs = ["franca_parser_test.py"],
    data = ["//score/parsers/franca_parser/test/parser/test_data:fidl_files"],
    deps = ["//score/parsers/franca_parser"],
)
