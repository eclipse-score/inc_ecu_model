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

"""Bazel rule for merging model registry pickle outputs from parser targets."""

def _load_and_merge_impl(ctx):
    registry_files = []
    for parser_target in ctx.attr.parsers:
        target_files = parser_target[DefaultInfo].files.to_list()
        if len(target_files) != 1:
            fail("Parser target {} must provide exactly one registry pickle".format(parser_target.label))
        registry_files.extend(target_files)

    output_files = [ctx.outputs.out]
    args = ctx.actions.args()
    args.add_all(registry_files, before_each = "--registry-pickle")
    args.add("--output", ctx.outputs.out)
    if ctx.outputs.txt_out:
        args.add("--text-output", ctx.outputs.txt_out)
        output_files.append(ctx.outputs.txt_out)

    ctx.actions.run(
        executable = ctx.executable._runner,
        inputs = registry_files,
        outputs = output_files,
        arguments = [args],
        mnemonic = "LoadAndMergeModels",
        progress_message = "Loading and merging IDL models for %{label}",
    )

    return [DefaultInfo(files = depset(output_files))]

load_and_merge = rule(
    implementation = _load_and_merge_impl,
    attrs = {
        "out": attr.output(mandatory = True, doc = "Final model pickle output."),
        "parsers": attr.label_list(
            allow_files = True,
            doc = "Targets each producing one pickle serialized by ModelRegistry.serialize().",
        ),
        "txt_out": attr.output(doc = "Optional human-readable merged output."),
        "_runner": attr.label(
            default = Label("//score/parsers/runner:run_load_and_merge"),
            executable = True,
            cfg = "exec",
        ),
    },
)
