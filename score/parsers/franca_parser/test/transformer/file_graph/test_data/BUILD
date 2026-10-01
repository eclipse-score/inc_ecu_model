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

filegroup(
    name = "fidl_files",
    srcs = glob(["*.fidl"]),
    visibility = ["//visibility:public"],
)

filegroup(
    name = "direct_import_root",
    srcs = ["root_imports_types.fidl"],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "direct_import_dependency",
    srcs = ["imported_types.fidl"],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "import_cycle_root",
    srcs = ["left_cycle.fidl"],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "import_cycle_dependency",
    srcs = ["right_cycle.fidl"],
    visibility = ["//visibility:public"],
)
