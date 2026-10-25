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

"""Tests for trusted-pickle loading and generator dispatch."""

import os
import pickle
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from score.ecu_model.model import ModelElement, ModelRegistry
from score.generators.src import generator_runner


class GeneratorRunnerTest(unittest.TestCase):
    """Exercise dispatch through the runner's public interface."""

    def setUp(self):
        """Isolate the model objects created by the test fixtures."""
        ModelRegistry.elements.clear()
        self.addCleanup(ModelRegistry.elements.clear)

    def test_generators_run_in_order_with_one_loaded_model_and_shared_output(self):
        """All generators receive the identical model and output root in order."""
        calls = []

        class FirstGenerator:
            def generate(self, model, output_dir):
                calls.append(("first", model, output_dir))
                (output_dir / "first.txt").write_text("first", encoding="utf-8")

        class SecondGenerator:
            def generate(self, model, output_dir):
                calls.append(("second", model, output_dir))
                (output_dir / "second.txt").write_text("second", encoding="utf-8")

        with tempfile.TemporaryDirectory() as temporary_directory:
            input_path = Path(temporary_directory) / "model.pkl"
            element = ModelElement(description="shared model element")
            model = {"data_types": {element.id: element}, "metadata": {"source": "merged"}}
            payload = pickle.dumps(model)
            input_path.write_bytes(payload)
            output_dir = Path(temporary_directory) / "nested" / "out"
            with (
                patch.object(generator_runner, "GENERATOR_FACTORIES", (FirstGenerator, SecondGenerator)),
                patch.object(generator_runner.pickle, "loads", wraps=pickle.loads) as loads,
            ):
                generator_runner.GeneratorRunner().run(input_path, output_dir)

            loads.assert_called_once_with(payload)
            self.assertEqual([call[0] for call in calls], ["first", "second"])
            self.assertEqual(calls[0][1], model)
            self.assertIs(calls[0][1], calls[1][1])
            self.assertIs(calls[0][2], output_dir)
            self.assertIs(calls[1][2], output_dir)
            self.assertEqual((output_dir / "first.txt").read_text(encoding="utf-8"), "first")
            self.assertEqual((output_dir / "second.txt").read_text(encoding="utf-8"), "second")

    def test_each_invocation_creates_fresh_generator_instances(self):
        """Generator state does not leak between runner invocations."""
        instances = []

        class RecordingGenerator:
            def __init__(self):
                instances.append(self)

            def generate(self, model, output_dir):
                pass

        with tempfile.TemporaryDirectory() as temporary_directory:
            input_path = Path(temporary_directory) / "model.pkl"
            input_path.write_bytes(pickle.dumps({"data_types": {}}))
            output_dir = Path(temporary_directory) / "out"
            with patch.object(generator_runner, "GENERATOR_FACTORIES", (RecordingGenerator,)):
                runner = generator_runner.GeneratorRunner()
                runner.run(input_path, output_dir)
                runner.run(input_path, output_dir)

        self.assertEqual(len(instances), 2)
        self.assertIsNot(instances[0], instances[1])

    def test_generation_failure_identifies_generator_and_stops_subsequent_calls(self):
        """The first failed generator aborts the remaining dispatch."""
        calls = []
        failure = ValueError("invalid datatype")

        class FailingGenerator:
            def generate(self, model, output_dir):
                calls.append("failing")
                raise failure

        class LaterGenerator:
            def generate(self, model, output_dir):
                calls.append("later")

        with tempfile.TemporaryDirectory() as temporary_directory:
            input_path = Path(temporary_directory) / "model.pkl"
            input_path.write_bytes(pickle.dumps({"data_types": {}}))
            output_dir = Path(temporary_directory) / "out"
            with (
                patch.object(generator_runner, "GENERATOR_FACTORIES", (FailingGenerator, LaterGenerator)),
                self.assertRaisesRegex(RuntimeError, "FailingGenerator generation failed") as raised,
            ):
                generator_runner.GeneratorRunner().run(input_path, output_dir)

        self.assertIs(raised.exception.__cause__, failure)
        self.assertEqual(calls, ["failing"])

    def test_loading_failure_prevents_constructing_generators(self):
        """Missing files and corrupt pickles never reach a generator."""
        instances = []

        class UnexpectedGenerator:
            def __init__(self):
                instances.append(self)

            def generate(self, model, output_dir):
                pass

        scenarios = (
            ("missing", None, FileNotFoundError),
            ("corrupt", b"not a pickle", pickle.UnpicklingError),
        )
        for name, contents, error_type in scenarios:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary_directory:
                input_path = Path(temporary_directory) / "model.pkl"
                if contents is not None:
                    input_path.write_bytes(contents)
                output_dir = Path(temporary_directory) / "out"
                with (
                    patch.object(generator_runner, "GENERATOR_FACTORIES", (UnexpectedGenerator,)),
                    self.assertRaises(error_type),
                ):
                    generator_runner.GeneratorRunner().run(input_path, output_dir)
                self.assertFalse(output_dir.exists())

        self.assertEqual(instances, [])

    def test_model_access_errors_are_preserved(self):
        """Model access failures reach the runner with their original exception types."""
        for model, error_type in ((["not", "a", "model"], TypeError), ({uuid4(): ModelElement()}, KeyError)):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as temporary_directory:
                input_path = Path(temporary_directory) / "model.pkl"
                input_path.write_bytes(pickle.dumps(model))
                output_dir = Path(temporary_directory) / "out"

                with self.assertRaisesRegex(RuntimeError, "DatatypeGenerator generation failed") as raised:
                    generator_runner.GeneratorRunner().run(input_path, output_dir)

                self.assertIsInstance(raised.exception.__cause__, error_type)

    def test_empty_registration_creates_output_root(self):
        """An explicitly empty registration list produces no artifacts."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            input_path = Path(temporary_directory) / "model.pkl"
            input_path.write_bytes(pickle.dumps({"data_types": {}}))
            output_dir = Path(temporary_directory) / "out"
            with patch.object(generator_runner, "GENERATOR_FACTORIES", ()):
                generator_runner.GeneratorRunner().run(input_path, output_dir)

            self.assertTrue(output_dir.is_dir())
            self.assertEqual(list(output_dir.iterdir()), [])

    def test_main_passes_parsed_paths_to_runner(self):
        """The CLI forwards both required paths as Path objects."""
        arguments = ["generator_runner", "--input", "model.pkl", "--output-dir", "generated"]
        with patch.object(sys, "argv", arguments), patch.object(generator_runner.GeneratorRunner, "run") as run:
            generator_runner.main()

        run.assert_called_once_with(Path("model.pkl"), Path("generated"))

    def test_cli_returns_nonzero_when_pickle_loading_fails(self):
        """An uncaught loading error fails the generator process."""
        executable = (
            Path(os.environ["TEST_SRCDIR"]) / os.environ["TEST_WORKSPACE"] / "score/generators/generator_runner"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            input_path = Path(temporary_directory) / "model.pkl"
            input_path.write_bytes(b"not a pickle")
            output_dir = Path(temporary_directory) / "out"
            result = subprocess.run(
                [
                    str(executable),
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(output_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("UnpicklingError", result.stderr)
            self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
