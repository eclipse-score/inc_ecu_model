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

"""Rule parsing Franca files and Protobuf descriptor sets into one pickled ECU model."""

load("@protobuf//bazel/common:proto_info.bzl", "ProtoInfo")

def _ecu_model_parse_impl(ctx):
    descriptor_sets = depset(transitive = [
        protobuf_dep[ProtoInfo].transitive_descriptor_sets
        for protobuf_dep in ctx.attr.protobuf_deps
    ])
    output = ctx.actions.declare_file(ctx.label.name + ".pkl")

    args = ctx.actions.args()
    args.add_all(ctx.files.franca_srcs, before_each = "--franca-src")
    args.add_all(ctx.files.franca_deps, before_each = "--franca-dep")
    args.add_all(descriptor_sets, before_each = "--descriptor-set")
    args.add("--output", output)
    args.add("--log-level", ctx.attr.log_level)

    ctx.actions.run(
        executable = ctx.executable._runner,
        inputs = depset(ctx.files.franca_srcs + ctx.files.franca_deps, transitive = [descriptor_sets]),
        outputs = [output],
        arguments = [args],
        mnemonic = "EcuModelParse",
        progress_message = "Parsing ECU model %{label}",
    )
    return [DefaultInfo(files = depset([output]))]

ecu_model_parse = rule(
    implementation = _ecu_model_parse_impl,
    doc = "Runs all parsers in parallel and writes the serialized ModelRegistry (ModelRegistry.serialize()) to <name>.pkl.",
    attrs = {
        "franca_deps": attr.label_list(
            allow_files = [".fidl", ".fdepl"],
            doc = "FIDL/FDEPL files the sources may import.",
        ),
        "franca_srcs": attr.label_list(
            allow_files = [".fidl", ".fdepl"],
            doc = "Root FIDL/FDEPL files.",
        ),
        "log_level": attr.string(
            default = "WARNING",
            values = ["DEBUG", "INFO", "WARNING", "ERROR"],
            doc = "Log level of the parse action; INFO shows per-parser timing in the build output.",
        ),
        "protobuf_deps": attr.label_list(
            providers = [ProtoInfo],
            doc = "proto_library targets whose transitive descriptor sets are parsed.",
        ),
        "_runner": attr.label(
            default = Label("//score/orchestrator:run_load_dispatch"),
            cfg = "exec",
            executable = True,
        ),
    },
)
