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

"""Run the IDL parsers in parallel child processes and merge their results into one ECU model."""

from __future__ import annotations

from pathlib import Path
import logging
from logging.handlers import QueueHandler, QueueListener
import pickle
import tempfile
import time
from multiprocessing import get_context
from multiprocessing.process import BaseProcess
from typing import Any

from score.ecu_model.model import ModelRegistry
from score.orchestrator.common import Parser, ParsingPathInfo
from score.orchestrator.parser_adapter import FrancaAdapter, ProtobufAdapter

_logger = logging.getLogger(__name__)


class _ForwardToLocalLogger(logging.Handler):
    """Re-emit log records of child processes through the logger of the same name in this process."""

    def emit(self, record: logging.LogRecord) -> None:
        logger = logging.getLogger(record.name)
        if logger.isEnabledFor(record.levelno):
            logger.handle(record)


def _run_parser(
    parser_class: type[Parser], path_info: ParsingPathInfo, result_path: Path, log_queue: Any, log_level: int
) -> None:
    """
    Child process entry point: run one parser and pickle its outcome.

    The payload is either {"registry": ...} with the elements this parser created, or {"error": ...} if parsing
    failed. Errors are reported via the payload so the parent can name the failing parser.

    Args:
        parser_class: Adapter to instantiate.
        path_info: Input files of the parser.
        result_path: File the payload is written to.
        log_queue: Queue all log records of this process are sent to.
        log_level: Effective logging level inherited from the orchestrator in the parent process.
    """
    # Spawned children have no logging setup; filter records before forwarding them to the parent.
    root_logger = logging.getLogger()
    root_logger.addHandler(QueueHandler(log_queue))
    root_logger.setLevel(log_level)
    try:
        known_ids = set(ModelRegistry.elements)
        parser_class(path_info).run()
        # A forked child inherits the parent's registry; ship only what this parser created.
        created = {uuid: element for uuid, element in ModelRegistry.elements.items() if uuid not in known_ids}
        payload: dict[str, Any] = {"registry": created}
    except Exception as error:
        payload = {"error": f"{type(error).__name__}: {error}"}
    with result_path.open("wb") as result_file:
        pickle.dump(payload, result_file, protocol=pickle.HIGHEST_PROTOCOL)


def _collect(name: str, process: BaseProcess, result_path: Path) -> dict[str, Any]:
    """
    Wait for a parser process and load its payload.

    Args:
        name: Parser name used in error messages.
        process: Started parser process.
        result_path: File the process writes its payload to.

    Returns:
        The successful payload with "registry".

    Raises:
        RuntimeError: If the process crashed, wrote no payload, or reported a parser error.
    """
    process.join()
    if process.exitcode != 0:
        raise RuntimeError(f"{name}: process exited with code {process.exitcode}")
    if not result_path.exists():
        raise RuntimeError(f"{name}: result file missing")
    with result_path.open("rb") as result_file:
        payload = pickle.load(result_file)
    if "error" in payload:
        raise RuntimeError(f"{name}: {payload['error']}")
    return payload


def _merge(payloads: list[dict[str, Any]]) -> None:
    """Add all parser results to the model registry."""
    for payload in payloads:
        ModelRegistry.merge(payload["registry"])


def load_and_parse(
    franca: ParsingPathInfo = ParsingPathInfo(),
    protobuf: ParsingPathInfo = ParsingPathInfo(),
) -> None:
    """
    Run each parser that has source files in its own child process and add all model elements they create to
    ModelRegistry.

    Args:
        franca: FIDL/FDEPL files for the Franca parser.
        protobuf: protoc descriptor sets for the Protobuf parser.

    Raises:
        RuntimeError: If any parser fails.
        ValueError: If model element IDs collide while merging parser results.
    """
    candidates: tuple[tuple[type[Parser], ParsingPathInfo], ...] = (
        (FrancaAdapter, franca),
        (ProtobufAdapter, protobuf),
    )
    start = time.perf_counter()
    jobs: list[tuple[type[Parser], ParsingPathInfo]] = []
    for parser_class, path_info in candidates:
        if path_info.src_files:
            jobs.append((parser_class, path_info))
        else:
            _logger.debug("Skipping %s parser: no source files", parser_class.name)
    # spawn gives each child a fresh interpreter and thus an empty registry.
    context = get_context("spawn")
    log_level = _logger.getEffectiveLevel()
    log_listener = QueueListener(context.Queue(), _ForwardToLocalLogger())
    log_listener.start()
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            processes: dict[str, tuple[BaseProcess, Path]] = {}
            for parser_class, path_info in jobs:
                result_path = Path(temp_dir) / f"{parser_class.name}_result.pkl"
                process = context.Process(
                    target=_run_parser,
                    name=f"{parser_class.name}_parser",
                    args=(parser_class, path_info, result_path, log_listener.queue, log_level),
                )
                process.start()
                processes[parser_class.name] = (process, result_path)

            payloads: list[dict[str, Any]] = []
            errors: list[str] = []
            for name, (process, result_path) in processes.items():
                try:
                    payloads.append(_collect(name, process, result_path))
                except RuntimeError as error:
                    errors.append(str(error))
    finally:
        # Flushes pending child records, so they are logged before anything that follows.
        log_listener.stop()
    if errors:
        raise RuntimeError(f"Parser dispatch failed: {'; '.join(errors)}")
    _merge(payloads)
    _logger.info(
        "Merged %d model element(s) of %d parser(s) in %.2f s",
        sum(len(payload["registry"]) for payload in payloads),
        len(payloads),
        time.perf_counter() - start,
    )
