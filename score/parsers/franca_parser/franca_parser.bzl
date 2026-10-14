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

"""Bazel rules for collecting and parsing Franca FIDL files."""

load("//score/parsers/runner:parser_outputs.bzl", "ParserOutputsInfo")

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

def _franca_model_parser_impl(ctx):
    direct_sources = []
    dependency_sources = []

    for src in ctx.attr.srcs:
        if FrancaInfo in src:
            direct_sources.extend(src[FrancaInfo].direct_sources.to_list())
            dependency_sources.extend(src[FrancaInfo].transitive_sources.to_list())
        elif hasattr(src, "files"):
            direct_sources.extend(src.files.to_list())

    for dep in ctx.attr.deps:
        if FrancaInfo in dep:
            dependency_sources.extend(dep[FrancaInfo].transitive_sources.to_list())
        elif hasattr(dep, "files"):
            dependency_sources.extend(dep.files.to_list())

    direct_by_path = {file.path: file for file in direct_sources}
    direct_sources = [direct_by_path[path] for path in sorted(direct_by_path)]
    dependency_by_path = {
        file.path: file
        for file in dependency_sources
        if file.path not in direct_by_path
    }
    dependency_sources = [dependency_by_path[path] for path in sorted(dependency_by_path)]

    registry_file = ctx.actions.declare_file(ctx.label.name + "_registry.pkl")
    outputs = [registry_file]

    args = ctx.actions.args()
    args.add_all(direct_sources, before_each = "--src")
    args.add_all(dependency_sources, before_each = "--dep")
    args.add("--registry-output", registry_file)

    ctx.actions.run(
        executable = ctx.executable._parser_runner,
        inputs = direct_sources + dependency_sources,
        outputs = outputs,
        arguments = [args],
        mnemonic = "FrancaModelParser",
        progress_message = "Parsing Franca model for %{label}",
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

_franca_model_parser = rule(
    implementation = _franca_model_parser_impl,
    attrs = {
        "srcs": attr.label_list(allow_files = True),
        "deps": attr.label_list(allow_files = True),
        "_parser_runner": attr.label(
            default = Label("//score/parsers/franca_parser:franca_model_parser_runner"),
            cfg = "exec",
            executable = True,
        ),
    },
)

def franca_parse(name, srcs, deps = [], **kwargs):
    """Create a cached Franca model parser action with a registry output."""
    _franca_model_parser(
        name = name,
        srcs = srcs,
        deps = deps,
        **kwargs
    )
    native.filegroup(
        name = name + "_registry",
        srcs = [":" + name],
        output_group = "registry",
    )
