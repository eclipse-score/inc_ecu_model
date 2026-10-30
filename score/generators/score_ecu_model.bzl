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

"""Generate ECU-model artifacts and expose separate header-only C++ libraries."""

load("@rules_cc//cc:defs.bzl", "CcInfo", "cc_library")
load("@rules_cc//cc/common:cc_common.bzl", "cc_common")

def _score_ecu_model_artifacts_impl(ctx):
    artifacts = ctx.actions.declare_directory(ctx.label.name + "/out")
    args = ctx.actions.args()
    args.add("--input", ctx.file.model)
    args.add("--output-dir", artifacts.path)
    ctx.actions.run(
        executable = ctx.attr._runner[DefaultInfo].files_to_run,
        inputs = [ctx.file.model],
        outputs = [artifacts],
        arguments = [args],
        mnemonic = "GenerateScoreEcuModelArtifacts",
        progress_message = "Generate ECU-model artifacts for {}".format(ctx.label),
    )
    headers = depset([artifacts])
    return [
        DefaultInfo(files = headers),
        CcInfo(compilation_context = cc_common.create_compilation_context(
            headers = headers,
            system_includes = depset([artifacts.path]),
        )),
    ]

score_ecu_model_artifacts = rule(
    implementation = _score_ecu_model_artifacts_impl,
    doc = "Generate artifacts from a final model pickle and expose their output directory.",
    attrs = {
        "model": attr.label(
            mandatory = True,
            allow_single_file = [".pkl"],
            doc = "Target providing one trusted ECU-model pickle with resolved references.",
        ),
        "_runner": attr.label(
            default = Label("//score/generators:generator_runner"),
            cfg = "exec",
            executable = True,
        ),
    },
)

def cc_score_ecu_model_library(name, artifacts, **kwargs):
    """Expose previously generated headers to transitive C++ consumers.

    Args:
        name: Name of the header-only C++ library.
        artifacts: Label of a score_ecu_model_artifacts target supplying generated headers.
        **kwargs: Additional cc_library attributes, including deps and visibility.
    """
    cc_library(
        name = name,
        deps = [artifacts] + kwargs.pop("deps", []),
        **kwargs
    )
