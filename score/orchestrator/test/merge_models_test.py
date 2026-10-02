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

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from score.ecu_model.data_types.common import DataTypeSource
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.model import ModelRegistry
from score.ecu_model.query import datatypes_by_name
from score.orchestrator.merge_models import main


def write_partial_model(path: Path, namespace: str, *names: str) -> Path:
    """Write a partial model declaring one struct per name, as a separate parser action would."""
    ModelRegistry.elements.clear()
    for name in names:
        StructDataType(name=name, namespace=namespace, source_kind=DataTypeSource.PROTOBUF)
    path.write_bytes(ModelRegistry.serialize())
    ModelRegistry.elements.clear()
    return path


class MergeModelsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_registry = dict(ModelRegistry.elements)
        ModelRegistry.elements.clear()
        self._temp_dir = TemporaryDirectory()
        self._directory = Path(self._temp_dir.name)
        self._output = self._directory / "merged.pkl"

    def tearDown(self) -> None:
        self._temp_dir.cleanup()
        ModelRegistry.elements.clear()
        ModelRegistry.elements.update(self._saved_registry)

    def test_main_given_two_partial_models_expect_all_datatypes_merged(self) -> None:
        first = write_partial_model(self._directory / "first.pkl", "first", "Value")
        second = write_partial_model(self._directory / "second.pkl", "second", "Value", "Other")

        main(["--model", str(first), "--model", str(second), "--output", str(self._output)])

        ModelRegistry.elements.clear()
        ModelRegistry.deserialize(self._output.read_bytes())
        self.assertEqual(set(datatypes_by_name()), {"first.Value", "second.Value", "second.Other"})

    def test_main_given_same_datatype_name_in_two_partial_models_expect_error_and_no_output(self) -> None:
        first = write_partial_model(self._directory / "first.pkl", "shared", "Value")
        second = write_partial_model(self._directory / "second.pkl", "shared", "Value")

        with self.assertRaisesRegex(ValueError, "Duplicate datatype name: shared.Value"):
            main(["--model", str(first), "--model", str(second), "--output", str(self._output)])

        self.assertFalse(self._output.exists())

    def test_main_given_same_partial_model_twice_expect_duplicate_instance_error(self) -> None:
        partial = write_partial_model(self._directory / "partial.pkl", "example", "Value")

        with self.assertRaisesRegex(ValueError, "Duplicate instances"):
            main(["--model", str(partial), "--model", str(partial), "--output", str(self._output)])

    def test_main_given_info_level_expect_merge_logged(self) -> None:
        first = write_partial_model(self._directory / "first.pkl", "first", "Value")
        second = write_partial_model(self._directory / "second.pkl", "second", "Value")

        with self.assertLogs("score.orchestrator", level="INFO") as logs:
            main(["--model", str(first), "--model", str(second), "--output", str(self._output)])

        self.assertEqual(len(logs.output), 1)
        self.assertRegex(logs.output[0], r"Merged 2 model element\(s\) of 2 partial model\(s\) in \d+\.\d{2} s")


if __name__ == "__main__":
    unittest.main()
