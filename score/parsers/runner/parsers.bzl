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

"""Bazel rule for dispatching and parsing various IDL source files into a unified model."""

load("@rules_proto//proto:defs.bzl", "ProtoInfo")

def _load_dispatch_parse_impl(ctx):
    franca_files = []
    for src in ctx.attr.franca_srcs:
        if hasattr(src, "FrancaInfo") or "FrancaInfo" in dir(src):
            # In Starlark, we check if provider key is in src
            pass

        # Standard provider or DefaultInfo check
        if hasattr(src, "files"):
            franca_files.extend(src.files.to_list())

    # Deduplicate franca files
    franca_files = list({f.path: f for f in franca_files}.values())

    proto_descriptors = []
    for dep in ctx.attr.protobuf_deps:
        if ProtoInfo in dep:
            proto_descriptors.extend(dep[ProtoInfo].transitive_descriptor_sets.to_list())
        elif hasattr(dep, "files"):
            proto_descriptors.extend(dep.files.to_list())

    manifest_file = ctx.actions.declare_file(ctx.label.name + "_manifest.json")
    manifest_data = {
        "franca_files": [f.path for f in franca_files],
        "protobuf_files": [f.path for f in proto_descriptors],
    }
    ctx.actions.write(
        output = manifest_file,
        content = json.encode_indent(manifest_data, indent = "  "),
    )

    pickle_output_file = ctx.outputs.out if ctx.outputs.out else ctx.actions.declare_file(ctx.label.name + "_output.pkl")
    text_output_file = ctx.outputs.txt_out if ctx.outputs.txt_out else ctx.actions.declare_file(ctx.label.name + "_output.txt")

    all_inputs = depset(
        direct = [manifest_file] + franca_files + proto_descriptors,
    )

    args = ctx.actions.args()
    args.add("--manifest", manifest_file)
    args.add("--output", pickle_output_file)
    args.add("--text-output", text_output_file)

    ctx.actions.run(
        executable = ctx.executable._runner,
        inputs = all_inputs,
        outputs = [pickle_output_file, text_output_file],
        arguments = [args],
        mnemonic = "LoadDispatchParser",
        progress_message = "Parsing IDL sources for %{label}",
    )

    return [
        DefaultInfo(
            files = depset([pickle_output_file, text_output_file]),
            runfiles = ctx.runfiles(files = [pickle_output_file, text_output_file, manifest_file]),
        ),
    ]

load_dispatch_parse = rule(
    implementation = _load_dispatch_parse_impl,
    attrs = {
        "franca_srcs": attr.label_list(
            allow_files = True,
            doc = "Franca source files (e.g. .fidl, .fdepl)",
        ),
        "out": attr.output(
            doc = "Optional pickle output file",
        ),
        "txt_out": attr.output(
            doc = "Optional human-readable text output file",
        ),
        "protobuf_deps": attr.label_list(
            doc = "Protobuf dependencies or descriptor sets",
        ),
        "_runner": attr.label(
            default = Label("//score/parsers/runner:run_load_dispatch"),
            executable = True,
            cfg = "exec",
        ),
    },
)
