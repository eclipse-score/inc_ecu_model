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

import json
import os
import pickle
import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from score.ecu_model.architecture.activity import Activity
from score.ecu_model.communication.service_interface import Broadcast
from score.ecu_model.data_types.identifier import Identifier
from score.ecu_model.model import ModelElement, ModelRegistry
from score.parsers.runner.load_and_merge import load_and_merge
from score.parsers.runner.run_load_and_merge import _stringify_keys, main


class TestLoadAndMerge(unittest.TestCase):
    def setUp(self) -> None:
        self.saved_registry = dict(ModelRegistry.elements)
        ModelRegistry.elements.clear()
        self.addCleanup(self.restore_registry)
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.directory = Path(temporary_directory.name)

    def restore_registry(self) -> None:
        ModelRegistry.elements.clear()
        ModelRegistry.elements.update(self.saved_registry)

    def write_registry(self, name: str, element: ModelElement) -> str:
        ModelRegistry.elements.clear()
        ModelRegistry.elements[element.id] = element
        path = self.directory / name
        path.write_bytes(ModelRegistry.serialize())
        return str(path)

    def run_merge(self, inputs: list[str], name: str) -> Path:
        output = self.directory / name
        arguments = [
            os.environ["MERGE_RUNNER"],
            "--output",
            str(output),
            "--text-output",
            str(output.with_suffix(".json")),
        ]
        for registry_path in inputs:
            arguments.extend(["--registry-pickle", registry_path])
        completed = subprocess.run(arguments, capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return output

    def test_merges_arbitrary_number_of_registries(self) -> None:
        elements = [ModelElement(description=str(index)) for index in range(5)]
        inputs = [self.write_registry(f"parser_{index}.pkl", element) for index, element in enumerate(elements)]

        result = load_and_merge(inputs)

        expected = {element.id: element for element in elements}
        self.assertEqual(ModelRegistry.elements, expected)
        self.assertEqual(result["data_types"], expected)

    def test_single_registry(self) -> None:
        element = ModelElement(description="single")
        registry = self.write_registry("single.pkl", element)

        load_and_merge([registry])

        self.assertEqual(ModelRegistry.elements, {element.id: element})

    def test_empty_list_clears_registry(self) -> None:
        ModelElement(description="stale")

        self.assertEqual(load_and_merge([]), {"data_types": {}})
        self.assertEqual(ModelRegistry.elements, {})

    def test_missing_file_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Registry pickle file missing"):
            load_and_merge([str(self.directory / "missing.pkl")])

    def test_non_registry_pickle_is_rejected(self) -> None:
        path = self.directory / "invalid.pkl"
        path.write_bytes(pickle.dumps({"data_types": {}}))

        with self.assertRaisesRegex(RuntimeError, "Payload does not contain a ModelRegistry"):
            load_and_merge([str(path)])

    def test_duplicate_element_ids_are_rejected(self) -> None:
        element = ModelElement()
        first = self.write_registry("first.pkl", element)
        second = self.write_registry("second.pkl", element)

        with self.assertRaisesRegex(RuntimeError, "Duplicate model element ID"):
            load_and_merge([first, second])

    def test_cli_merges_model_types_into_final_result(self) -> None:
        elements = [
            ModelElement(description="generic parser"),
            Activity(name=Identifier("Activity")),
            Broadcast(name=Identifier("Event")),
        ]
        inputs = [self.write_registry(f"parser_{index}.pkl", element) for index, element in enumerate(elements)]

        output = self.run_merge(inputs, "merged.pkl")

        result = pickle.loads(output.read_bytes())
        self.assertEqual(result, {"data_types": {element.id: element for element in elements}})
        text = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
        self.assertEqual(set(text), {"data_types"})
        self.assertEqual(set(text["data_types"]), {str(element.id) for element in elements})
        self.assertEqual(text, json.loads(json.dumps(_stringify_keys(result), default=str)))

    def test_cli_final_result_is_not_a_raw_registry_input(self) -> None:
        element = ModelElement(description="parser")
        registry = self.write_registry("parser.pkl", element)
        output = self.run_merge([registry], "merged.pkl")

        with self.assertRaisesRegex(RuntimeError, "Payload does not contain a ModelRegistry"):
            load_and_merge([str(output)])

    def test_cli_empty_list_writes_empty_result(self) -> None:
        output = self.run_merge([], "empty.pkl")

        self.assertEqual(pickle.loads(output.read_bytes()), {"data_types": {}})

    def invoke_main(self, arguments: list[str], workspace: str = "") -> None:
        with (
            patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": workspace}),
            patch("sys.argv", ["run_load_and_merge", *arguments]),
        ):
            main()

    def test_main_merges_repeated_inputs_and_creates_output_directories(self) -> None:
        first = ModelElement(description="first")
        second = ModelElement(description="second")
        first_input = self.write_registry("first.pkl", first)
        second_input = self.write_registry("second.pkl", second)
        output = self.directory / "binary" / "merged.pkl"
        text_output = self.directory / "text" / "merged.json"

        self.invoke_main(
            [
                "--registry-pickle",
                first_input,
                "--registry-pickle",
                second_input,
                "--output",
                str(output),
                "--text-output",
                str(text_output),
            ]
        )

        self.assertEqual(pickle.loads(output.read_bytes()), {"data_types": {first.id: first, second.id: second}})
        self.assertEqual(ModelRegistry.elements, {first.id: first, second.id: second})
        text = json.loads(text_output.read_text(encoding="utf-8"))
        self.assertEqual(set(text["data_types"]), {str(first.id), str(second.id)})

    def test_main_without_text_output_writes_only_pickle(self) -> None:
        output = self.directory / "binary" / "empty.pkl"

        self.invoke_main(["--output", str(output)])

        self.assertEqual(pickle.loads(output.read_bytes()), {"data_types": {}})
        self.assertEqual(list(output.parent.iterdir()), [output])

    def test_main_resolves_relative_outputs_against_workspace(self) -> None:
        self.invoke_main(
            ["--output", "binary/merged.pkl", "--text-output", "text/merged.json"],
            workspace=str(self.directory),
        )

        self.assertEqual(pickle.loads((self.directory / "binary/merged.pkl").read_bytes()), {"data_types": {}})
        self.assertEqual(
            json.loads((self.directory / "text/merged.json").read_text(encoding="utf-8")),
            {"data_types": {}},
        )

    def test_main_preserves_absolute_outputs_with_workspace(self) -> None:
        output = self.directory / "absolute" / "merged.pkl"
        text_output = self.directory / "absolute" / "merged.json"
        workspace = self.directory / "workspace"

        self.invoke_main(
            ["--output", str(output), "--text-output", str(text_output)],
            workspace=str(workspace),
        )

        self.assertEqual(pickle.loads(output.read_bytes()), {"data_types": {}})
        self.assertTrue(text_output.is_file())
        self.assertFalse(workspace.exists())

    def test_main_workspace_without_text_output(self) -> None:
        self.invoke_main(["--output", "merged.pkl"], workspace=str(self.directory))

        self.assertEqual(pickle.loads((self.directory / "merged.pkl").read_bytes()), {"data_types": {}})

    def test_main_requires_output_argument(self) -> None:
        with patch("sys.stderr"), self.assertRaises(SystemExit) as raised:
            self.invoke_main([])

        self.assertEqual(raised.exception.code, 2)

    def test_main_propagates_invalid_input_without_writing_output(self) -> None:
        output = self.directory / "merged.pkl"

        with self.assertRaisesRegex(RuntimeError, "Registry pickle file missing"):
            self.invoke_main(["--registry-pickle", str(self.directory / "missing.pkl"), "--output", str(output)])

        self.assertFalse(output.exists())

    def test_script_entry_point_writes_final_result(self) -> None:
        output = self.directory / "script.pkl"
        script = Path(__file__).parents[1] / "run_load_and_merge.py"

        with (
            patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": ""}),
            patch("sys.argv", [str(script), "--output", str(output)]),
        ):
            run_path(str(script), run_name="__main__")

        self.assertEqual(pickle.loads(output.read_bytes()), {"data_types": {}})


class TestStringifyKeys(unittest.TestCase):
    def test_primitive_values_are_preserved(self) -> None:
        for value in [None, True, False, 0, 42, 1.25, "text"]:
            with self.subTest(value=value):
                self.assertIs(_stringify_keys(value), value)

    def test_dictionary_keys_are_stringified_recursively(self) -> None:
        identifier = UUID(int=1)

        self.assertEqual(_stringify_keys({identifier: {2: "value"}}), {str(identifier): {"2": "value"}})

    def test_sequence_types_are_converted_to_lists(self) -> None:
        for value in [[1, 2], (1, 2), {1, 2}, frozenset({1, 2})]:
            with self.subTest(value=value):
                converted = _stringify_keys(value)
                self.assertIsInstance(converted, list)
                self.assertCountEqual(converted, [1, 2])

    def test_dataclass_fields_are_converted_recursively(self) -> None:
        @dataclass
        class Record:
            payload: object

        self.assertEqual(_stringify_keys(Record({1: ("value",)})), {"payload": {"1": ["value"]}})

    def test_pydantic_fields_are_converted_recursively(self) -> None:
        event = Broadcast(name=Identifier("Event"))
        self.addCleanup(ModelRegistry.elements.pop, event.id)

        self.assertEqual(
            _stringify_keys(event),
            {"id": event.id, "description": "", "name": {"root": "Event"}, "outputs": []},
        )

    def test_object_attributes_are_converted_recursively(self) -> None:
        self.assertEqual(_stringify_keys(SimpleNamespace(payload={1: (2,)})), {"payload": {"1": [2]}})

    def test_unsupported_value_is_preserved_for_json_fallback(self) -> None:
        identifier = UUID(int=1)

        self.assertIs(_stringify_keys(identifier), identifier)

    def test_cycles_are_marked(self) -> None:
        cyclic: list[object] = []
        cyclic.append(cyclic)

        self.assertEqual(_stringify_keys(cyclic), ["..."])

    def test_shared_values_are_not_mistaken_for_cycles(self) -> None:
        shared = {1: "value"}
        active_object_ids: set[int] = set()

        self.assertEqual(_stringify_keys([shared, shared], active_object_ids), [{"1": "value"}, {"1": "value"}])
        self.assertEqual(active_object_ids, set())


if __name__ == "__main__":
    unittest.main()
