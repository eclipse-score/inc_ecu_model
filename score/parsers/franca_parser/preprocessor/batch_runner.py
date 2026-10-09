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

"""
Preprocess Franca files concurrently in batches.

Entry points
----
There are two ways to start preprocessing:

1. Instantiate :class:`BatchRunner` with the input paths and options, then call method `batch_run` of `BatchRunner`
   class.
2. Call the `batch_preprocess` function with the program arguments. It converts those arguments into a `BatchRunner`
   class instance and ultimately calls its `batch_run` method of `BatchRunner` class.

Concurrency model
----
The preprocessor uses two levels of concurrency to process large collections of Franca files faster. At the first level,
multiple processes handle files concurrently, making use of multiple CPU cores. At the second level, each process starts
multiple threads. The threads can overlap file processing with loading other files, so I/O waits in one thread do not
leave the process idle.
"""

import argparse
import ctypes
import json
import os
import pickle
import queue
import time
import traceback
from datetime import datetime
from multiprocessing import Process, Queue as MPQueue, Value
from pathlib import Path
from threading import Thread, current_thread, get_ident
from typing import Any, Iterable, Optional, Sequence, TypedDict

from score.parsers.franca_parser.preprocessor.preprocess import preprocess

DEFAULT_BATCH_SIZE = 10
DEFAULT_QUEUE_TIMEOUT = 0.5
DEFAULT_WORKER_THREAD_COUNT = 5
MAX_PREPROCESSOR_PROCESS_COUNT = 10
FRANCA_FILE_EXTENSIONS = {".fidl", ".fcdl", ".fdepl", ".cdepl", ".fsdl"}


class BatchPreProcessError(Exception):
    """Raised when a batch worker fails to preprocess a file."""


class WorkerError(TypedDict):
    """Serializable details for an exception raised by a preprocessor worker."""

    process_id: int
    thread_id: int
    thread_name: str
    timestamp: str
    file_path: str | None
    exception_type: str
    message: str
    traceback: str


class PreProcessorWorker(Thread):
    """Read file batches, preprocess their contents, and return processed batches."""

    def __init__(
        self,
        in_queue_file_list: Any,
        out_queue_processed_files: Any,
        error_queue: Any,
        all_paths_sent: Any,
        defines: set[str],
        batch_size: int = DEFAULT_BATCH_SIZE,
        queue_timeout: float = DEFAULT_QUEUE_TIMEOUT,
    ) -> None:
        """Read file batches, preprocess their contents, and return processed batches.

        :param in_queue_file_list: Queue from which batches of paths are read.
        :param out_queue_processed_files: Queue receiving processed file batches.
        :param error_queue: Queue receiving details about worker failures.
        :param all_paths_sent: Shared flag indicating that no more paths will arrive.
        :param defines: Symbols treated as defined during preprocessing.
        :param batch_size: Maximum number of results sent in one output batch.
        :param queue_timeout: Maximum wait between input queue checks.
        """
        super().__init__(daemon=True)
        self.in_queue_file_list = in_queue_file_list
        self.out_queue_processed_files = out_queue_processed_files
        self.error_queue = error_queue
        self.all_paths_sent = all_paths_sent
        self.defines = defines
        self.batch_size = batch_size
        self.queue_timeout = queue_timeout

    def run(self) -> None:
        """Process queued files and report results or any worker failure."""
        batch_processed: list[tuple[str, str]] = []
        current_file: str | None = None
        try:
            while True:
                try:
                    file_batch = self.in_queue_file_list.get(timeout=self.queue_timeout)
                except queue.Empty:
                    if self.all_paths_sent.value:
                        break
                    continue

                if file_batch is None:
                    self.all_paths_sent.value = True
                    break
                if not isinstance(file_batch, (list, tuple, set)):
                    raise ValueError(f"Expected a list, tuple, or set of file paths, got {type(file_batch)}")

                for file_path in file_batch:
                    file_path_abs = Path(file_path).resolve()
                    current_file = str(file_path_abs)
                    try:
                        raw_content = file_path_abs.read_text(encoding="utf-8")
                        processed_content = preprocess(raw_content, self.defines)
                    except Exception as error:
                        raise BatchPreProcessError(f"Failed to process file: {file_path_abs}") from error

                    batch_processed.append((str(file_path_abs), processed_content))
                    current_file = None
                    if len(batch_processed) >= self.batch_size:
                        self.out_queue_processed_files.put(batch_processed)
                        batch_processed = []
        except Exception as error:
            if batch_processed:
                self.out_queue_processed_files.put(batch_processed)
            self.error_queue.put(
                WorkerError(
                    process_id=os.getpid(),
                    thread_id=get_ident(),
                    thread_name=current_thread().name,
                    timestamp=datetime.now().astimezone().isoformat(),
                    file_path=current_file,
                    exception_type=type(error).__name__,
                    message=str(error),
                    traceback=traceback.format_exc(),
                )
            )
            return

        if batch_processed:
            self.out_queue_processed_files.put(batch_processed)


class PreProcessorRunner(Process):
    """Run a pool of preprocessor worker threads in a child process."""

    def __init__(
        self,
        in_queue_file_list: Any,
        out_queue_processed_files: Any,
        error_queue: Any,
        all_paths_sent: Any,
        defines: set[str],
        thread_count: int = DEFAULT_WORKER_THREAD_COUNT,
        batch_size: int = DEFAULT_BATCH_SIZE,
        queue_timeout: float = DEFAULT_QUEUE_TIMEOUT,
    ) -> None:
        """Run a pool of preprocessor worker threads in a child process.

        :param in_queue_file_list: Queue from which batches of paths are read.
        :param out_queue_processed_files: Queue receiving processed file batches.
        :param error_queue: Queue receiving details about worker failures.
        :param all_paths_sent: Shared flag indicating that no more paths will arrive.
        :param defines: Symbols treated as defined during preprocessing.
        :param thread_count: Number of worker threads to start.
        :param batch_size: Maximum number of results sent in one output batch.
        :param queue_timeout: Maximum wait between input queue checks.
        """
        super().__init__()
        self.in_queue_file_list = in_queue_file_list
        self.out_queue_processed_files = out_queue_processed_files
        self.error_queue = error_queue
        self.all_paths_sent = all_paths_sent
        self.defines = defines
        self.thread_count = thread_count
        self.batch_size = batch_size
        self.queue_timeout = queue_timeout

    def run(self) -> None:
        """Start the configured workers and wait for them to finish."""
        workers = [
            PreProcessorWorker(
                in_queue_file_list=self.in_queue_file_list,
                out_queue_processed_files=self.out_queue_processed_files,
                error_queue=self.error_queue,
                all_paths_sent=self.all_paths_sent,
                defines=self.defines,
                batch_size=self.batch_size,
                queue_timeout=self.queue_timeout,
            )
            for _ in range(self.thread_count)
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()


def parse_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse batch-runner options.

    :param args: Optional command-line arguments to parse instead of process arguments.
    :return: The parsed batch-runner options.
    """
    parser = argparse.ArgumentParser(description="Batch runner for Franca source file preprocessing.")
    parser.add_argument("--dir", nargs="+", action="extend", default=[])
    parser.add_argument("--files", nargs="+", action="extend", default=[])
    parser.add_argument("--dir-path-file", default=None)
    parser.add_argument("--file-path-file", default=None)
    parser.add_argument("--recur", action="store_true", default=False)
    parser.add_argument("--defined", "-D", nargs="+", action="extend", default=[])
    parser.add_argument("--debug-output", type=Path, default=None)
    return parser.parse_args(args)


class BatchRunner:
    """Schedule and collect preprocessing for explicitly listed Franca files. See the docstring of this module for
    detail.
    """

    def __init__(
        self,
        dir_list: Optional[Iterable[str | Path]] = None,
        dir_path_file: Optional[str | Path] = None,
        file_list: Optional[Iterable[str | Path]] = None,
        file_path_file: Optional[str | Path] = None,
        recur: bool = False,
        defined_list: Optional[Sequence[str]] = None,
    ) -> None:
        """Schedule and collect preprocessing for explicitly listed Franca files. See the docstring of this module for
        detail.

        :param dir_list: Directories to search for source files.
        :param dir_path_file: File containing directories to search.
        :param file_list: Explicit source file paths to process.
        :param file_path_file: File containing explicit source file paths.
        :param recur: Whether directory searches include subdirectories.
        :param defined_list: Symbols treated as defined during preprocessing.
        """
        self.dir_list = [Path(directory) for directory in dir_list] if dir_list else []
        self.dir_path_file = Path(dir_path_file) if dir_path_file else None
        self.file_list = [Path(file_path) for file_path in file_list] if file_list else []
        self.file_path_file = Path(file_path_file) if file_path_file else None
        self.recur = recur
        self.defined_list = list(defined_list or [])
        self.out_queue_file_list: MPQueue = MPQueue()
        self.in_queue_processed_files: MPQueue = MPQueue()
        self.error_queue: MPQueue = MPQueue()
        self.all_paths_sent: Any = Value(ctypes.c_bool, False, lock=False)
        self.debug_info: dict[str, int | float | None] = {}

    def get_file_paths(
        self,
        batch_size: int = DEFAULT_BATCH_SIZE,
        sentinel_count: int = 1,
    ) -> None:
        """Discover supported input files and enqueue them with completion markers.

        :param batch_size: Maximum number of paths placed in each input batch.
        :param sentinel_count: Number of end-of-input markers to enqueue.
        """
        seen_paths: set[Path] = set()
        batch: list[Path] = []
        num_read_files = 0

        def handle_path(path: Path) -> None:
            """Add a unique supported path to the current input batch.

            :param path: Candidate source file path.
            """
            nonlocal batch, num_read_files
            resolved_path = path.resolve()
            if resolved_path in seen_paths:
                return
            seen_paths.add(resolved_path)
            num_read_files += 1
            batch.append(resolved_path)
            if len(batch) >= batch_size:
                self.out_queue_file_list.put(batch)
                batch = []

        if self.file_path_file:
            self.file_list.extend(Path(line.strip()) for line in self.file_path_file.read_text().splitlines())
        for file_path in self.file_list:
            if file_path.is_file() and file_path.suffix in FRANCA_FILE_EXTENSIONS:
                handle_path(file_path)

        if self.dir_path_file:
            self.dir_list.extend(Path(line.strip()) for line in self.dir_path_file.read_text().splitlines())
        for directory in self.dir_list:
            if not directory.is_dir():
                continue
            paths = directory.rglob("*") if self.recur else directory.iterdir()
            for path in paths:
                if path.is_file() and path.suffix in FRANCA_FILE_EXTENSIONS:
                    handle_path(path)

        if batch:
            self.out_queue_file_list.put(batch)
        self.debug_info["num_read_files"] = num_read_files
        for _ in range(sentinel_count):
            self.out_queue_file_list.put(None)

    def batch_run(self, batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, str]:
        """Run preprocessing across worker processes and collect all results.

        :param batch_size: Maximum number of files assigned to a processing batch.
        :return: A mapping from resolved file paths to preprocessed contents.
        :raises BatchPreProcessError: If one or more workers report a failure.
        """
        real_cpu_count = os.cpu_count()
        num_processes = min(MAX_PREPROCESSOR_PROCESS_COUNT, real_cpu_count or 4)
        sentinel_count = num_processes * DEFAULT_WORKER_THREAD_COUNT
        self.debug_info["real_cpu_count"] = real_cpu_count
        self.debug_info["num_processes"] = num_processes
        defines = set(self.defined_list)

        processes = [
            PreProcessorRunner(
                in_queue_file_list=self.out_queue_file_list,
                out_queue_processed_files=self.in_queue_processed_files,
                error_queue=self.error_queue,
                all_paths_sent=self.all_paths_sent,
                defines=defines,
                batch_size=batch_size,
            )
            for _ in range(num_processes)
        ]
        for process in processes:
            process.start()

        finder_thread = Thread(
            target=self.get_file_paths,
            kwargs={"batch_size": batch_size, "sentinel_count": sentinel_count},
            daemon=True,
        )
        finder_thread.start()

        result: dict[str, str] = {}
        while True:
            try:
                processed_batch = self.in_queue_processed_files.get(timeout=DEFAULT_QUEUE_TIMEOUT)
                result.update(processed_batch)
            except queue.Empty:
                if any(process.is_alive() for process in processes):
                    continue
                while not self.in_queue_processed_files.empty():
                    try:
                        result.update(self.in_queue_processed_files.get_nowait())
                    except queue.Empty:
                        break
                break

        finder_thread.join()
        for process in processes:
            process.join()
        self.debug_info["num_processed_files"] = len(result)
        errors: list[WorkerError] = []
        while True:
            try:
                errors.append(self.error_queue.get_nowait())
            except queue.Empty:
                break
        if errors:
            formatted_errors = "\n\n".join(
                f"Worker error {index} of {len(errors)}: "
                f"{error['exception_type']}: {error['message']}\n"
                f"Process {error['process_id']}, thread {error['thread_name']} "
                f"(ID {error['thread_id']}), at {error['timestamp']}\n"
                f"File: {error['file_path'] or '<unknown>'}\n"
                f"{error['traceback'].rstrip()}"
                for index, error in enumerate(errors, start=1)
            )
            raise BatchPreProcessError(
                f"{len(errors)} preprocessing worker error(s) occurred:\n\n{formatted_errors}"
            )
        return result


def batch_preprocess(prog_args: Optional[list[str]] = None) -> dict[str, str]:
    """Run batch preprocessing using command-line options.

    See the docstring of this module for detail.

    :param prog_args: Optional command-line arguments to parse instead of process arguments.
    :return: A mapping from resolved file paths to preprocessed contents.
    """
    script_start_time = time.time()
    args = parse_args(prog_args)
    runner = BatchRunner(
        dir_list=args.dir,
        dir_path_file=args.dir_path_file,
        file_list=args.files,
        file_path_file=args.file_path_file,
        recur=args.recur,
        defined_list=args.defined,
    )
    batch_run_start_time = time.time()
    result = runner.batch_run()
    batch_run_end_time = time.time()

    if args.debug_output is not None:
        debug_dir = args.debug_output
        debug_dir.mkdir(parents=True, exist_ok=True)
        with (debug_dir / "franca_preprocessed_result.pkl").open("wb") as pickle_file:
            pickle.dump(result, pickle_file)
        if result:
            file_path, content = next(iter(result.items()))
            (debug_dir / "example_processed_file.txt").write_text(
                f"File path: {file_path}\n\n{content}",
                encoding="utf-8",
            )
        log_data = {
            "script_started_at": datetime.fromtimestamp(script_start_time).isoformat(),
            "batch_run_started_at": datetime.fromtimestamp(batch_run_start_time).isoformat(),
            "batch_run_duration (seconds)": batch_run_end_time - batch_run_start_time,
            "num_read_files": runner.debug_info.get("num_read_files", 0),
            "num_processed_files": runner.debug_info.get("num_processed_files", 0),
            "real_cpu_count": runner.debug_info.get("real_cpu_count"),
            "num_processes": runner.debug_info.get("num_processes"),
        }
        with (debug_dir / "franca_preprocessed_log.json").open("w", encoding="utf-8") as log_file:
            json.dump(log_data, log_file, indent=4)
            log_file.write("\n")

    return result


if __name__ == "__main__":
    batch_preprocess()
