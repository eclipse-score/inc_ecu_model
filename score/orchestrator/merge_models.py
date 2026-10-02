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

"""Command line entry point: merge partial models into one serialized ModelRegistry."""

from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Sequence
from pathlib import Path

from score.ecu_model.model import ModelRegistry

_logger = logging.getLogger(__name__)


def main(arguments: Sequence[str] | None = None) -> None:
    """
    Merge the given partial models and write ModelRegistry.serialize() to the output file.

    Args:
        arguments: Command line arguments; sys.argv[1:] if None.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", required=True, type=Path, help="Partial model file to merge")
    parser.add_argument("--output", required=True, type=Path, help="Merged model file to write")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parsed = parser.parse_args(arguments)

    logging.basicConfig(level=parsed.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    start = time.perf_counter()
    for model in parsed.model:
        _logger.debug("Merged %d model element(s) from %s", ModelRegistry.merge_serialized(model.read_bytes()), model)
    parsed.output.write_bytes(ModelRegistry.serialize())
    _logger.info(
        "Merged %d model element(s) of %d partial model(s) in %.2f s",
        len(ModelRegistry.elements),
        len(parsed.model),
        time.perf_counter() - start,
    )


if __name__ == "__main__":
    main()
