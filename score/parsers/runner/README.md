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

The dispatcher is implemented in `load_dispatch.py`. Each adapter runs in a
separate spawned process and writes its `ModelRegistry` as a pickle file. When
`return_parsed_object` is true, the parent merges those registries and returns
the serialized registry bytes. When it is false, callers must provide output
paths through the corresponding `ParsingPathInfo` values, which receive each
adapter's serialized registry.

The adapters live in `score/parsers/franca_parser` and
`score/parsers/protobuf_parser`. Runner rules and entry points are in this
package, with integration input targets under `test/int`.