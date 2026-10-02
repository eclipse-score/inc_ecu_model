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

"""Public API ecu_model_parse: builds an ECU model from IDL inputs, one Bazel action per parser."""

load("@protobuf//bazel/common:proto_info.bzl", "ProtoInfo")

EcuModelInfo = provider(
    doc = "A full or partial ECU model.",
    fields = {"model": "File holding the serialized ModelRegistry (ModelRegistry.serialize())."},
)

_LOG_LEVEL_ATTR = attr.string(
    default = "WARNING",
    values = ["DEBUG", "INFO", "WARNING", "ERROR"],
    doc = "Log level of the action; INFO shows timing and element counts in the build output.",
)

_PARSER_ATTR = attr.label(
    default = Label("//score/orchestrator:run_parser"),
    cfg = "exec",
    executable = True,
)

def _run_parser(ctx, parser, srcs, deps):
    output = ctx.actions.declare_file(ctx.label.name + ".pkl")
    args = ctx.actions.args()
    args.add("--parser", parser)
    args.add_all(srcs, before_each = "--src")
    args.add_all(deps, before_each = "--dep")
    args.add("--output", output)
    args.add("--log-level", ctx.attr.log_level)
    ctx.actions.run(
        executable = ctx.executable._parser,
        inputs = depset(transitive = [srcs, deps]),
        outputs = [output],
        arguments = [args],
        mnemonic = parser.capitalize() + "Model",
        progress_message = "Parsing " + parser + " model %{label}",
    )
    return [DefaultInfo(files = depset([output])), EcuModelInfo(model = output)]

def _franca_model_impl(ctx):
    return _run_parser(ctx, "franca", depset(ctx.files.srcs), depset(ctx.files.deps))

_franca_model = rule(
    implementation = _franca_model_impl,
    doc = "Parses FIDL/FDEPL files into a partial model <name>.pkl.",
    attrs = {
        "deps": attr.label_list(allow_files = [".fidl", ".fdepl"], doc = "FIDL/FDEPL files the sources may import."),
        "log_level": _LOG_LEVEL_ATTR,
        "srcs": attr.label_list(allow_files = [".fidl", ".fdepl"], mandatory = True, doc = "Root FIDL/FDEPL files."),
        "_parser": _PARSER_ATTR,
    },
)

def _protobuf_model_impl(ctx):
    descriptor_sets = depset(transitive = [dep[ProtoInfo].transitive_descriptor_sets for dep in ctx.attr.deps])
    return _run_parser(ctx, "protobuf", descriptor_sets, depset())

_protobuf_model = rule(
    implementation = _protobuf_model_impl,
    doc = "Parses the transitive descriptor sets of proto_library targets into a partial model <name>.pkl.",
    attrs = {
        "deps": attr.label_list(providers = [ProtoInfo], mandatory = True, doc = "proto_library targets."),
        "log_level": _LOG_LEVEL_ATTR,
        "_parser": _PARSER_ATTR,
    },
)

def _ecu_model_merge_impl(ctx):
    models = [model[EcuModelInfo].model for model in ctx.attr.models]
    output = ctx.actions.declare_file(ctx.label.name + ".pkl")
    args = ctx.actions.args()
    args.add_all(models, before_each = "--model")
    args.add("--output", output)
    args.add("--log-level", ctx.attr.log_level)
    ctx.actions.run(
        executable = ctx.executable._merger,
        inputs = models,
        outputs = [output],
        arguments = [args],
        mnemonic = "EcuModelMerge",
        progress_message = "Merging ECU model %{label}",
    )
    return [DefaultInfo(files = depset([output])), EcuModelInfo(model = output)]

_ecu_model_merge = rule(
    implementation = _ecu_model_merge_impl,
    doc = "Merges full or partial models into <name>.pkl and checks the result with ModelRegistry.finalize().",
    attrs = {
        "log_level": _LOG_LEVEL_ATTR,
        "models": attr.label_list(providers = [EcuModelInfo], mandatory = True, doc = "Models to merge."),
        "_merger": attr.label(
            default = Label("//score/orchestrator:merge_models"),
            cfg = "exec",
            executable = True,
        ),
    },
)

def franca_inputs(srcs, deps = []):
    """Inputs of the Franca parser for ecu_model_parse.

    Args:
        srcs: Root FIDL/FDEPL files.
        deps: FIDL/FDEPL files the sources may import; only parsed when reached via imports.
    """
    if not srcs:
        fail("franca_inputs needs srcs")
    return struct(parser = "franca", srcs = srcs, deps = deps)

def protobuf_inputs(deps):
    """Inputs of the Protobuf parser for ecu_model_parse.

    Args:
        deps: proto_library targets whose transitive descriptor sets are parsed.
    """
    if not deps:
        fail("protobuf_inputs needs deps")
    return struct(parser = "protobuf", deps = deps)

def _checked(inputs, parser, helper):
    if inputs and getattr(inputs, "parser", None) != parser:
        fail("ecu_model_parse: {} must be created with {}()".format(parser, helper))
    return inputs

def ecu_model_parse(name, franca = None, protobuf = None, log_level = "WARNING", **kwargs):
    """Creates the ECU model <name>.pkl, running only the parsers whose inputs are given.

    Every parser runs in its own Bazel action. With inputs for more than one parser, their partial models
    <name>_<parser> are merged into <name>.

    Args:
        name: Name of the model target.
        franca: franca_inputs() for the Franca parser, or None to skip it.
        protobuf: protobuf_inputs() for the Protobuf parser, or None to skip it.
        log_level: Log level of all actions.
        **kwargs: Common attributes like testonly or visibility, applied to all targets.
    """
    parsers = []
    if _checked(franca, "franca", "franca_inputs"):
        parsers.append(("franca", _franca_model, {"deps": franca.deps, "srcs": franca.srcs}))
    if _checked(protobuf, "protobuf", "protobuf_inputs"):
        parsers.append(("protobuf", _protobuf_model, {"deps": protobuf.deps}))
    if not parsers:
        fail("ecu_model_parse needs franca or protobuf inputs")

    if len(parsers) == 1:
        _, parser_rule, attrs = parsers[0]
        parser_rule(name = name, log_level = log_level, **dict(attrs, **kwargs))
        return
    for parser, parser_rule, attrs in parsers:
        parser_rule(name = name + "_" + parser, log_level = log_level, **dict(attrs, **kwargs))
    _ecu_model_merge(
        name = name,
        models = [":" + name + "_" + parser for parser, _, _ in parsers],
        log_level = log_level,
        **kwargs
    )
