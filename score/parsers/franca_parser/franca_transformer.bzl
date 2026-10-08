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

"""Rules for transforming Franca FIDL files."""

FrancaInfo = provider(
    doc = "Encapsulates Franca FIDL and FDEPL source files and their transitive dependencies",
    fields = {
        "direct_sources": "depset of direct .fidl / .fdepl files",
        "transitive_sources": "depset of all direct and transitive .fidl / .fdepl files",
    },
)

def _franca_library_impl(ctx):
    transitive_deps = []
    for dep in ctx.attr.deps:
        if FrancaInfo in dep:
            transitive_deps.append(dep[FrancaInfo].transitive_sources)
        elif hasattr(dep, "files"):
            transitive_deps.append(dep.files)

    direct_files = depset(ctx.files.srcs)
    all_files = depset(direct = ctx.files.srcs, transitive = transitive_deps)

    return [
        DefaultInfo(files = all_files),
        FrancaInfo(
            direct_sources = direct_files,
            transitive_sources = all_files,
        ),
    ]

franca_library = rule(
    implementation = _franca_library_impl,
    doc = "Defines a library of Franca files with transitive dependency support.",
    attrs = {
        "srcs": attr.label_list(allow_files = [".fidl", ".fdepl", ".cdepl"]),
        "deps": attr.label_list(allow_files = True),
    },
)

def _franca_transformer_impl(ctx):
    args = ctx.actions.args()

    direct_srcs = []
    for src in ctx.attr.srcs:
        if FrancaInfo in src:
            direct_srcs.extend(src[FrancaInfo].direct_sources.to_list())
        elif hasattr(src, "files"):
            direct_srcs.extend(src.files.to_list())

    transitive_deps = []
    for dep in ctx.attr.deps:
        if FrancaInfo in dep:
            transitive_deps.extend(dep[FrancaInfo].transitive_sources.to_list())
        elif hasattr(dep, "files"):
            transitive_deps.extend(dep.files.to_list())

    src_files = list({f.path: f for f in direct_srcs}.values())
    dep_files = list({f.path: f for f in transitive_deps if f not in src_files}.values())

    for source in src_files:
        args.add("--src", source.path)
    for dependency in dep_files:
        args.add("--dep", dependency.path)
    args.add("--out", ctx.outputs.transformed_franca_files.path)

    ctx.actions.run(
        inputs = src_files + dep_files,
        outputs = [ctx.outputs.transformed_franca_files],
        arguments = [args],
        executable = ctx.executable._runner,
        mnemonic = "FrancaTransformer",
        progress_message = "Transform Franca FIDL files {}".format(ctx.label),
    )
    return DefaultInfo(files = depset([ctx.outputs.transformed_franca_files]))

_franca_transformer = rule(
    implementation = _franca_transformer_impl,
    attrs = {
        "deps": attr.label_list(allow_files = True),
        "srcs": attr.label_list(allow_files = [".fidl", ".fdepl", ".cdepl"]),
        "transformed_franca_files": attr.output(mandatory = True),
        "_runner": attr.label(
            default = Label("//score/parsers/franca_parser:franca_transformer_runner"),
            cfg = "exec",
            executable = True,
        ),
    },
)

def franca_transformer(name, srcs, deps = [], **kwargs):
    _franca_transformer(
        name = name,
        srcs = srcs,
        deps = deps,
        transformed_franca_files = name + "_franca_parser/gen/" + name + "_transformed_franca_files.pkl",
        **kwargs
    )
