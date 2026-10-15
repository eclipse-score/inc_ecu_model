# Parser Runner

The load-and-merge runner combines model artifacts produced by independent
Franca and Protobuf Bazel parser targets. Bazel schedules and caches each parser
action; the Python runner only loads and merges their pickle outputs.

## Bazel targets

- `franca_parse` in `franca_parser.bzl` creates a Franca model parser
  target.
- `protobuf_parse` in `proto_parser.bzl` creates a Protobuf model parser
  target.
- `//score/parsers/runner:run_load_and_merge` accepts registry pickle outputs
  from parser targets.
- `//score/parsers/runner/test/int/runner:load_and_merge_demo` runs the
  runner with the repository's Franca and Protobuf integration fixtures.
- `//score/parsers/runner/test/int/runner:load_and_merge_build_demo` exposes
  parsed outputs as Bazel artifacts for downstream targets.

Run the integration demo as a smoke check:

```sh
bazel run //score/parsers/runner/test/int/runner:load_and_merge_demo
```

Build the rule-based parsing demo and its output artifacts with:

```sh
bazel build //score/parsers/runner/test/int/runner:load_and_merge_build_demo
```

Each parser target emits a `ModelRegistry` pickle. The runner validates and
merges the registry artifacts, then writes the aggregate pickle as
`{"data_types": registry}` and can optionally write its text representation.

Parser rules and adapters live in `score/parsers/franca_parser` and
`score/parsers/protobuf_parser`. Runner rules and entry points are in this
package, with integration input targets under `test/int`.