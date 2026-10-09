# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.

# This program and the accompanying materials are made available under the
# terms of the Apache License Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
# *******************************************************************************

from __future__ import annotations

from functools import wraps
from multiprocessing import get_context, Process
from pathlib import Path
import pickle
from queue import Empty
import tempfile
from typing import Any
from score.parsers.runner.common import Parser, ParsingPathInfo

from score.parsers.franca_parser.parser import WrapperFrancaParser
from score.parsers.protobuf_parser.api import (
    WrapperProtobufParser,
)

ParserResult = dict[str, object]



def _run_parser_process(
    parser_name: str,
    parser_class: type[Parser],
    files_desc: ParsingPathInfo,
    status_queue: Any,
) -> None:
    """Run a parser in a child process and report completion to the parent.

    :param parser_name: Label included in the completion notification.
    :param parser_class: Parser implementation to instantiate.
    :param files_desc: Source paths, output path, and parser-specific metadata.
    :param status_queue: Queue receiving the completion status.
    """
    try:
        # Check
        if files_desc.result_pickle_path is None:
            raise ValueError("The result_pickle_path cannot be None.")

        # Parse
        result = parser_class(files_desc).parse()
        # Performance consideration:
        #   * `parse()` returns the `result`
        #
        #     This function and the `parse()` method run in the same subprocess. So returning the result just returns
        #     a reference and hence is very cheap.
        #
        #   * This function writes file
        #
        #     However, if this function puts `result` into the `status_queue`, it would serialize the entire object into
        #     memory, which may bring significant overhead for large result objects. So this function writes `result`
        #     to a pickle file instead. The path of the pickle file is specified by the main process so it knows where
        #     to read the result from.

        # Report to the main process
        with Path(files_desc.result_pickle_path).open("wb") as output_file:
            pickle.dump(result, output_file)
        status_queue.put((parser_name, True, ""))
    except Exception as error:  # pragma: no cover
        status_queue.put((parser_name, False, f"{type(error).__name__}: {error}"))


def _prepare_temp_dir(func):
    """Provide and clean up a temporary directory when the caller supplies none.

    If the decorated function receives a non-empty ``temp_dir`` keyword argument,
    this decorator leaves that directory under the caller's control.

    :param func: Function to wrap with temporary-directory management.
    :return: A wrapper that supplies a temporary directory when needed.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        """Call the wrapped function with managed temporary storage when needed."""
        # We don't manage the user specified `temp_dir`
        if kwargs.get("temp_dir"):
            return func(*args, **kwargs)

        # Create and inject `temp_dir`, clean it up automatically after the function execution.
        with tempfile.TemporaryDirectory() as temp_dir:
            kwargs["temp_dir"] = temp_dir
            return func(*args, **kwargs)

    return wrapper

@_prepare_temp_dir
def load_and_parse(
    franca_files_desc: ParsingPathInfo,
    protobuf_files_desc: ParsingPathInfo,
    return_parsed_object: bool,
    temp_dir: str = "",
) -> dict[str, object]:
    """Parse Franca and Protobuf inputs in parallel and optionally merge their results.

    When parsed results are returned, missing output paths are created in a temporary
    directory. Otherwise, each input description must provide an output path.

    :param franca_files_desc: Description of the Franca files parsing.
    :param protobuf_files_desc: Description of the Protobuf files parsing.
    :param return_parsed_object: Whether to load and merge the parser results in this process.
    :param temp_dir: Directory for intermediate results; normally supplied automatically.
    :return: Merged parser data when requested, or an empty mapping otherwise.
    :raises ValueError: If results are not returned and an output path is missing.
    :raises RuntimeError: If a parser process fails or its result cannot be loaded.
    """
    # 1. Prepare
    # Define the specs
    parser_specs = {
        "franca": (WrapperFrancaParser, franca_files_desc),
        "protobuf": (WrapperProtobufParser, protobuf_files_desc),
    }

    # Validate the input
    for parser_name, (_, files_desc) in parser_specs.items():
        if files_desc.result_pickle_path is None:
            if return_parsed_object:
                # Write the result into a temp file
                files_desc.result_pickle_path = str(Path(temp_dir) / f"{parser_name}_result.pkl")
            else:
                # The `result_pickle_path` field must be provided.
                raise ValueError(f"Missing result_pickle_path for {parser_name}")


    # 2. Create and launch processes
    multiprocessing_context = get_context()
    status_queue = multiprocessing_context.Queue()
    processes: dict[str, Process] = {}

    for parser_name, (parser_class, files_desc) in parser_specs.items():
        process = multiprocessing_context.Process(
            target=_run_parser_process,
            name=f"{parser_name}_parser_process",
            args=(
                parser_name,
                parser_class,
                files_desc,
                status_queue,  # "task done" notification
            ),
        )
        processes[parser_name] = process
        process.start()

    # 3. Collect the result
    results: dict[str, ParserResult] = {}
    errors: dict[str, str] = {}

    pending_parser_names = set(processes)
    while pending_parser_names:
        # `status_queue` is `put` only when a sub-process have finished the parsing of all the source files.
        try:
            parser_name, success, error_message = status_queue.get(timeout=1)
        except Empty:
            for parser_name in tuple(pending_parser_names):
                process = processes[parser_name]
                if not process.is_alive():
                    errors[parser_name] = (
                        f"process exited with code {process.exitcode} without reporting status"
                    )
                    pending_parser_names.remove(parser_name)
            continue

        if parser_name not in pending_parser_names:
            continue
        pending_parser_names.remove(parser_name)

        # Error handling
        if not success:
            errors[parser_name] = error_message
            continue
        result_pickle_file = Path(parser_specs[parser_name][1].result_pickle_path)
        if not result_pickle_file.exists():
            errors[parser_name] = f"pickle output file missing: {result_pickle_file}"
            continue

        # Collect the result
        if return_parsed_object:
            try:
                with result_pickle_file.open("rb") as pickle_file:
                    results[parser_name] = pickle.load(pickle_file)
            except Exception as error:
                errors[parser_name] = f"failed to load pickle output: {error}"
        # Note:
        #   * If the `return_parsed_object` parameter of this function is `False`, the result pickle files generated by
        #     the subprocesses are just the final result and will be used by the caller of this function directly. This
        #     function does nothing in this case.
        #   * A typical usage is that these files are considered as the output of this Bazel taget and can be used by
        #     other Bazel targets that depend on this one.

    # 4. Post-processing
    # Wait for the termination of all the subprocesses
    for parser_name, process in processes.items():
        process.join()
        if process.exitcode not in (0, None) and parser_name not in errors:
            errors[parser_name] = f"process exited with code {process.exitcode}"

    # Handle the errors
    if errors:
        error_summary = "; ".join(f"{parser_name}: {message}" for parser_name, message in sorted(errors.items()))
        raise RuntimeError(f"Parser dispatch failed: {error_summary}")

    if not return_parsed_object:
        return {}

    merged_data_types: dict[str, object] = {}
    for parser_name in ("franca", "protobuf"):
        parser_result = results.get(parser_name, {})
        parser_data_types = parser_result.get("data_types", {})
        if isinstance(parser_data_types, dict):
            merged_data_types.update(parser_data_types)

    return {"data_types": merged_data_types}
