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

"""Bazel rules for parsing Protobuf descriptors into model artifacts."""

load("@rules_proto//proto:defs.bzl", "ProtoInfo")
load("//score/parsers/runner:parser_outputs.bzl", "ParserOutputsInfo")

def _proto_descriptor_sets_impl(ctx):
    descriptor_sets = depset(transitive = [
        protobuf_dep[ProtoInfo].transitive_descriptor_sets
        for protobuf_dep in ctx.attr.protobuf_deps
    ])
    return [DefaultInfo(files = descriptor_sets)]

proto_descriptor_sets = rule(
    implementation = _proto_descriptor_sets_impl,
    attrs = {
        "protobuf_deps": attr.label_list(
            mandatory = True,
            providers = [ProtoInfo],
        ),
    },
)

def _proto_parser_impl(ctx):
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

proto_parser = rule(
    implementation = _proto_parser_impl,
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

def _protobuf_model_parser_impl(ctx):
    descriptor_sets = []
    for protobuf_dep in ctx.attr.protobuf_deps:
        if ProtoInfo in protobuf_dep:
            descriptor_sets.extend(protobuf_dep[ProtoInfo].transitive_descriptor_sets.to_list())
        elif hasattr(protobuf_dep, "files"):
            descriptor_sets.extend(protobuf_dep.files.to_list())

    descriptor_by_path = {file.path: file for file in descriptor_sets}
    descriptor_sets = [descriptor_by_path[path] for path in sorted(descriptor_by_path)]

    registry_file = ctx.actions.declare_file(ctx.label.name + "_registry.pkl")
    outputs = [registry_file]

    args = ctx.actions.args()
    args.add_all(descriptor_sets, before_each = "--descriptor-set")
    args.add("--registry-output", registry_file)

    ctx.actions.run(
        executable = ctx.executable._parser_runner,
        inputs = descriptor_sets,
        outputs = outputs,
        arguments = [args],
        mnemonic = "ProtobufModelParser",
        progress_message = "Parsing Protobuf model for %{label}",
    )

    return [
        DefaultInfo(files = depset(outputs)),
        ParserOutputsInfo(
            registry_file = registry_file,
        ),
        OutputGroupInfo(
            registry = depset([registry_file]),
        ),
    ]

_protobuf_model_parser = rule(
    implementation = _protobuf_model_parser_impl,
    attrs = {
        "protobuf_deps": attr.label_list(allow_files = True),
        "_parser_runner": attr.label(
            default = Label("//score/parsers/protobuf_parser:protobuf_model_parser_runner"),
            cfg = "exec",
            executable = True,
        ),
    },
)

def protobuf_parse(name, protobuf_deps, **kwargs):
    """Create a cached Protobuf model parser action with a registry output."""
    _protobuf_model_parser(
        name = name,
        protobuf_deps = protobuf_deps,
        **kwargs
    )
    native.filegroup(
        name = name + "_registry",
        srcs = [":" + name],
        output_group = "registry",
    )
