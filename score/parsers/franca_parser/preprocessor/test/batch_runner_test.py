# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under
# the terms of the Apache License Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
# *******************************************************************************

"""Tests for multiprocessing batch preprocessing."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from score.parsers.franca_parser.preprocessor.batch_runner import (
    BatchPreProcessError,
    BatchRunner,
    PreProcessorRunner,
)


class BatchRunnerTest(unittest.TestCase):
    """Verify worker failures reach the parent process."""

    def test_batch_run_when_worker_thread_fails_raises_after_cleanup(self) -> None:
        """Verify a worker error is raised after all child processes are cleaned up."""
        with TemporaryDirectory() as temporary_directory:
            good_file = Path(temporary_directory) / "good.fidl"
            bad_file = Path(temporary_directory) / "bad.fidl"
            good_file.write_text("package good\n", encoding="utf-8")
            bad_file.write_text("#else\n", encoding="utf-8")

            processes: list[PreProcessorRunner] = []

            class RecordingPreProcessorRunner(PreProcessorRunner):
                def __init__(self, *args: object, **kwargs: object) -> None:
                    """Record each process instance while preserving normal setup."""
                    super().__init__(*args, **kwargs)
                    processes.append(self)

            runner = BatchRunner(file_list=[good_file, bad_file])
            with (
                patch(
                    "score.parsers.franca_parser.preprocessor.batch_runner.PreProcessorRunner",
                    RecordingPreProcessorRunner,
                ),
                patch("score.parsers.franca_parser.preprocessor.batch_runner.MAX_PREPROCESSOR_PROCESS_COUNT", 1),
                self.assertRaises(BatchPreProcessError) as error_context,
            ):
                runner.batch_run(batch_size=10)

        self.assertIn(str(bad_file.resolve()), str(error_context.exception))
        self.assertIn("Traceback (most recent call last)", str(error_context.exception))
        self.assertIn("PreProcessError: #else without previous #if", str(error_context.exception))
        self.assertRegex(str(error_context.exception), r"Process \d+, thread .+ \(ID \d+\), at .+")
        self.assertEqual(runner.debug_info["num_processed_files"], 1)
        self.assertEqual(len(processes), 1)
        self.assertFalse(processes[0].is_alive())
        self.assertEqual(processes[0].exitcode, 0)

    def test_batch_run_when_multiple_worker_threads_fail_reports_all_errors(self) -> None:
        """Verify failures from multiple workers are all included in the raised error."""
        with TemporaryDirectory() as temporary_directory:
            bad_files = [Path(temporary_directory) / f"bad_{index}.fidl" for index in range(2)]
            for bad_file in bad_files:
                bad_file.write_text("#else\n", encoding="utf-8")

            runner = BatchRunner(file_list=bad_files)
            with (
                patch("score.parsers.franca_parser.preprocessor.batch_runner.MAX_PREPROCESSOR_PROCESS_COUNT", 1),
                self.assertRaises(BatchPreProcessError) as error_context,
            ):
                runner.batch_run(batch_size=1)

        error_message = str(error_context.exception)
        self.assertIn("2 preprocessing worker error(s) occurred", error_message)
        for bad_file in bad_files:
            self.assertIn(str(bad_file.resolve()), error_message)


if __name__ == "__main__":
    unittest.main()