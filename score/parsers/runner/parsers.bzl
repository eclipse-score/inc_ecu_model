"""Bazel rule for merging outputs produced by individual parser targets."""

load(":parser_outputs.bzl", "ParserOutputsInfo")

def _load_and_merge_impl(ctx):
    registry_files = []
    for parser_target in ctx.attr.franca_parsers + ctx.attr.protobuf_parsers:
        parser_outputs = parser_target[ParserOutputsInfo]
        registry_files.append(parser_outputs.registry_file)

    pickle_output_file = ctx.outputs.out
    text_output_file = ctx.outputs.txt_out
    output_files = [pickle_output_file]

    args = ctx.actions.args()
    args.add_all(registry_files, before_each = "--registry-pickle")
    args.add("--output", pickle_output_file)
    if text_output_file:
        args.add("--text-output", text_output_file)
        output_files.append(text_output_file)

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
        "franca_parsers": attr.label_list(
            providers = [ParserOutputsInfo],
            doc = "Targets produced by Franca parser macros.",
        ),
        "protobuf_parsers": attr.label_list(
            providers = [ParserOutputsInfo],
            doc = "Targets produced by Protobuf parser macros.",
        ),
        "out": attr.output(
            mandatory = True,
            doc = "Merged registry pickle output file",
        ),
        "txt_out": attr.output(
            doc = "Optional human-readable merged registry output file",
        ),
        "_runner": attr.label(
            default = Label("//score/parsers/runner:run_load_and_merge"),
            executable = True,
            cfg = "exec",
        ),
    },
)
