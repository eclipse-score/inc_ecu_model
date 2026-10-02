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
import unittest

from score.ecu_model.model import ModelElement, ModelRegistry
from score.orchestrator.common import Parser, ParsingPathInfo


class _TwoElementParser(Parser):
    name = "fake"

    def parse(self) -> None:
        ModelElement()
        ModelElement()


class ParserRunTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_registry = dict(ModelRegistry.elements)

    def tearDown(self) -> None:
        ModelRegistry.elements.clear()
        ModelRegistry.elements.update(self._saved_registry)

    def test_run_given_parser_creating_two_elements_expect_start_and_finish_logged(self) -> None:
        path_info = ParsingPathInfo(src_files=(Path("a.idl"), Path("b.idl")), dependency_files=(Path("c.idl"),))

        with self.assertLogs("score.orchestrator.common", level="INFO") as logs:
            _TwoElementParser(path_info).run()

        self.assertEqual(len(logs.output), 2)
        self.assertIn("Starting fake parser with 2 source file(s) and 1 dependency file(s)", logs.output[0])
        self.assertRegex(logs.output[1], r"fake parser finished after \d+\.\d{2} s, created 2 model element\(s\)")

    def test_run_given_debug_level_expect_input_files_logged(self) -> None:
        path_info = ParsingPathInfo(src_files=(Path("a.idl"),), dependency_files=(Path("c.idl"),))

        with self.assertLogs("score.orchestrator.common", level="DEBUG") as logs:
            _TwoElementParser(path_info).run()

        self.assertIn("fake parser input files: a.idl, c.idl", logs.output[1])


if __name__ == "__main__":
    unittest.main()
