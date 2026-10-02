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

"""Example generator rule consuming a model built with the orchestrator rules."""

load("//score/orchestrator:ecu_model.bzl", "EcuModelInfo")

def _datatype_list_impl(ctx):
    model = ctx.attr.model[EcuModelInfo].model
    output = ctx.actions.declare_file(ctx.label.name + ".txt")

    args = ctx.actions.args()
    args.add("--model", model)
    args.add("--output", output)

    ctx.actions.run(
        executable = ctx.executable._generator,
        inputs = [model],
        outputs = [output],
        arguments = [args],
        mnemonic = "DatatypeList",
        progress_message = "Listing datatypes of %{label}",
    )
    return [DefaultInfo(files = depset([output]))]

datatype_list = rule(
    implementation = _datatype_list_impl,
    doc = "Writes one '<fully qualified name> <kind> <source>' line per datatype of a model to <name>.txt.",
    attrs = {
        "model": attr.label(
            mandatory = True,
            providers = [EcuModelInfo],
            doc = "ecu_model target.",
        ),
        "_generator": attr.label(
            default = Label("//score/generators/datatype_list"),
            cfg = "exec",
            executable = True,
        ),
    },
)
