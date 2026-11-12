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

py_test(
    name = "array_type_unit_test",
    size = "small",
    srcs = ["array_type_test.py"],
    main = "array_type_test.py",
    deps = [
        "//score/ecu_model",
        "//score/ecu_model/data_types",
        "//score/generators/src/datatypes:cpp_model",
        "//score/generators/src/datatypes:datatype_utils",
    ],
)

py_test(
    name = "enum_type_unit_test",
    size = "small",
    srcs = ["enum_type_test.py"],
    main = "enum_type_test.py",
    deps = [
        "//score/ecu_model",
        "//score/ecu_model/data_types",
        "//score/generators/src/datatypes:cpp_model",
        "//score/generators/src/datatypes:datatype_generator",
        "//score/generators/src/datatypes:datatype_utils",
    ],
)

py_test(
    name = "struct_type_unit_test",
    size = "small",
    srcs = ["struct_type_test.py"],
    main = "struct_type_test.py",
    deps = [
        "//score/ecu_model",
        "//score/ecu_model/data_types",
        "//score/generators/src/datatypes:cpp_model",
        "//score/generators/src/datatypes:datatype_generator",
        "//score/generators/src/datatypes:datatype_utils",
    ],
)

py_test(
    name = "typedef_type_unit_test",
    size = "small",
    srcs = ["typedef_type_test.py"],
    main = "typedef_type_test.py",
    deps = [
        "//score/ecu_model",
        "//score/ecu_model/data_types",
        "//score/generators/src/datatypes:cpp_model",
        "//score/generators/src/datatypes:datatype_generator",
        "//score/generators/src/datatypes:datatype_utils",
    ],
)

py_test(
    name = "union_type_unit_test",
    size = "small",
    srcs = ["union_type_test.py"],
    main = "union_type_test.py",
    deps = [
        "//score/ecu_model",
        "//score/ecu_model/data_types",
        "//score/generators/src/datatypes:cpp_model",
        "//score/generators/src/datatypes:datatype_utils",
    ],
)

py_test(
    name = "datatype_utils_unit_test",
    size = "small",
    srcs = ["datatype_utils_test.py"],
    main = "datatype_utils_test.py",
    deps = [
        "//score/ecu_model",
        "//score/ecu_model/data_types",
        "//score/generators/src/datatypes:cpp_model",
        "//score/generators/src/datatypes:datatype_collector",
        "//score/generators/src/datatypes:datatype_generator",
        "//score/generators/src/datatypes:datatype_utils",
    ],
)
