# Franca Interface Parsing

This package parses Franca files and transforms them into the shared ECU model.

## How to use

### Python

Use `FrancaParser` to parse the input files, then `FrancaFileGraphTransformer` to transform them:

```python
from score.parsers.franca_parser.parser import FrancaParser
from score.parsers.franca_parser.transformer.file_graph_transformer import FrancaFileGraphTransformer

parsed_files = FrancaParser(root_files, dependency_files).parse_files()
graph = FrancaFileGraphTransformer(parsed_files)
graph.transform_files()
```

### Bazel

Add the parser target to the target that runs the code:

```python
py_binary(
    name="my_app",
    srcs=["main.py"],
    deps=["//score/parsers/franca_parser:franca_parser"],
)
```

If the application directly imports shared ECU model types, add their targets as direct dependencies as well:
`//score/ecu_model/communication` for interfaces and members, `//score/ecu_model/data_types` for datatypes, and
`//score/ecu_model` for `ModelRegistry`.

## Tests

Run the parser test suite with:

```sh
bazel test --config=ruff //score/parsers/franca_parser/...
```

The parser-to-model integration test can also be run separately:

```sh
bazel test //score/parsers/franca_parser/test/parser:fidl_registry_integration_test --test_output=errors
```
