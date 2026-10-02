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

package(default_visibility = ["//visibility:public"])

filegroup(
    name = "deployment_root",
    srcs = ["datatype_properties_deployment.fdepl"],
)

filegroup(
    name = "deployment_dependencies",
    srcs = [
        "datatype_properties.fidl",
        "score_architecture_deployment_spec.fdepl",
        "score_network_SOMEIP_deployment_spec.fdepl",
    ],
)

filegroup(
    name = "deployment_files",
    srcs = glob([
        "*.fidl",
        "*.fdepl",
    ]),
)
