# Parser Runner

The runner dispatches Franca (`.fidl` and `.fdepl`) and Protobuf descriptor-set
inputs to their adapters in separate processes.

## Bazel targets

- `//score/parsers/runner:run_load_dispatch` accepts input file lists or a JSON
  manifest.
- `//score/parsers/runner/test/int/runner:load_dispatch_demo` runs the
  dispatcher with the repository's Franca and Protobuf integration fixtures.
- `//score/parsers/runner/test/int/runner:load_dispatch_parse_demo` exposes
  parsed outputs as Bazel artifacts for downstream targets.

Run the integration demo as a smoke check:

```sh
bazel run //score/parsers/runner/test/int/runner:load_dispatch_demo
```

Build the rule-based parsing demo and its output artifacts with:

```sh
bazel build //score/parsers/runner/test/int/runner:load_dispatch_parse_demo
```

The dispatcher is implemented in `load_dispatch.py`. Each adapter writes its
result to a pickle file; the parent process reads and returns the results when
`return_parsed_object` is true. When it is false, callers must provide output
paths through the corresponding `ParsingPathInfo` values.

The adapters live in `score/parsers/franca_parser` and
`score/parsers/protobuf_parser`. Runner rules and entry points are in this
package, with integration input targets under `test/int`.