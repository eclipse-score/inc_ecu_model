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

"""Command line entry point: parse all IDL inputs into one ECU model and write the serialized ModelRegistry."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from score.ecu_model.model import ModelRegistry
from score.orchestrator.common import ParsingPathInfo
from score.orchestrator.load_dispatch import load_and_parse


def main(arguments: Sequence[str] | None = None) -> None:
    """
    Parse the given inputs with load_and_parse() and write ModelRegistry.serialize() to the output file.

    Args:
        arguments: Command line arguments; sys.argv[1:] if None.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--franca-src", action="append", default=[], type=Path, help="Root FIDL/FDEPL file")
    parser.add_argument("--franca-dep", action="append", default=[], type=Path, help="Importable FIDL/FDEPL file")
    parser.add_argument("--descriptor-set", action="append", default=[], type=Path, help="protoc descriptor set")
    parser.add_argument("--output", required=True, type=Path, help="Pickle file to write")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parsed = parser.parse_args(arguments)

    logging.basicConfig(
        level=parsed.log_level,
        format="%(asctime)s %(levelname)s [%(processName)s] %(name)s: %(message)s",
    )
    load_and_parse(
        franca=ParsingPathInfo(src_files=tuple(parsed.franca_src), dependency_files=tuple(parsed.franca_dep)),
        protobuf=ParsingPathInfo(src_files=tuple(parsed.descriptor_set)),
    )
    parsed.output.write_bytes(ModelRegistry.serialize())


if __name__ == "__main__":
    main()
