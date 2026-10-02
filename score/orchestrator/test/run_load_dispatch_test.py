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

from score.ecu_model.data_types.common import DataTypeBase
from score.ecu_model.model import ModelRegistry
from score.orchestrator.run_load_dispatch import main
from score.test_data.inputs import write_descriptor_set, write_fidl


class RunLoadDispatchTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_registry = dict(ModelRegistry.elements)
        ModelRegistry.elements.clear()

    def tearDown(self) -> None:
        ModelRegistry.elements.clear()
        ModelRegistry.elements.update(self._saved_registry)

    def test_main_given_franca_and_descriptor_set_expect_whole_registry_serialized(self) -> None:
        with TemporaryDirectory() as directory:
            fidl = write_fidl(Path(directory), "example.franca", "Types", "Value")
            descriptor_set = write_descriptor_set(Path(directory), "example.proto", "Value")
            output = Path(directory) / "model.pkl"

            main(["--franca-src", str(fidl), "--descriptor-set", str(descriptor_set), "--output", str(output)])
            parsed_elements = dict(ModelRegistry.elements)
            ModelRegistry.elements.clear()

            ModelRegistry.deserialize(output.read_bytes())

        self.assertEqual(set(ModelRegistry.elements), set(parsed_elements))
        self.assertEqual(
            {
                element.fully_qualified_name
                for element in ModelRegistry.elements.values()
                if isinstance(element, DataTypeBase)
            },
            {"example.franca.Types.Value", "example.proto.Value"},
        )

    def test_main_given_no_output_expect_usage_error(self) -> None:
        with self.assertRaises(SystemExit):
            main(["--franca-src", "a.fidl"])


if __name__ == "__main__":
    unittest.main()
