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

from pathlib import Path
import pickle
from tempfile import TemporaryDirectory
import unittest

from score.ecu_model.model import ModelRegistry
from score.orchestrator.run_load_dispatch import main
from score.orchestrator.test.inputs import write_descriptor_set, write_fidl


class RunLoadDispatchTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_registry = dict(ModelRegistry.elements)
        ModelRegistry.elements.clear()

    def tearDown(self) -> None:
        ModelRegistry.elements.clear()
        ModelRegistry.elements.update(self._saved_registry)

    def test_main_given_franca_and_descriptor_set_expect_merged_datatypes_pickled(self) -> None:
        with TemporaryDirectory() as directory:
            fidl = write_fidl(Path(directory), "example.franca", "Types", "Value")
            descriptor_set = write_descriptor_set(Path(directory), "example.proto", "Value")
            output = Path(directory) / "model.pkl"

            main(["--franca-src", str(fidl), "--descriptor-set", str(descriptor_set), "--output", str(output)])

            result = pickle.loads(output.read_bytes())
        self.assertEqual(set(result["datatypes"]), {"example.franca.Types.Value", "example.proto.Value"})

    def test_main_given_no_output_expect_usage_error(self) -> None:
        with self.assertRaises(SystemExit):
            main(["--franca-src", "a.fidl"])


if __name__ == "__main__":
    unittest.main()
