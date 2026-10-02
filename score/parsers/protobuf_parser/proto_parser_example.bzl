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

"""Example rule showing how a Protobuf parser consumes ProtoInfo descriptors."""

load("@protobuf//bazel/common:proto_info.bzl", "ProtoInfo")

def _proto_parser_example_impl(ctx):
    descriptor_sets = depset(transitive = [
        protobuf_dep[ProtoInfo].transitive_descriptor_sets
        for protobuf_dep in ctx.attr.protobuf_deps
    ])
    output = ctx.actions.declare_file(ctx.label.name + ".pickle")

    args = ctx.actions.args()
    args.add("--output", output)
    args.add_all(descriptor_sets, before_each = "--descriptor-set")

    ctx.actions.run(
        executable = ctx.executable._proto_parser_runner,
        inputs = descriptor_sets,
        outputs = [output],
        arguments = [args],
        progress_message = "Parsing Protobuf SCORE ECU model %{label}",
    )

    return [DefaultInfo(files = depset([output]))]

proto_parser_example = rule(
    implementation = _proto_parser_example_impl,
    attrs = {
        "protobuf_deps": attr.label_list(
            mandatory = True,
            providers = [ProtoInfo],
        ),
        "_proto_parser_runner": attr.label(
            executable = True,
            cfg = "exec",
            default = Label("//score/parsers/protobuf_parser:proto_parser_runner"),
        ),
    },
)
