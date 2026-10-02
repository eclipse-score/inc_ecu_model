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

"""Command line entry point: run one parser and write its partial model as serialized ModelRegistry."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from score.ecu_model.model import ModelRegistry
from score.orchestrator.common import Parser, ParsingPathInfo
from score.orchestrator.parser_adapter import FrancaAdapter, ProtobufAdapter

PARSERS: dict[str, type[Parser]] = {parser.name: parser for parser in (FrancaAdapter, ProtobufAdapter)}


def main(arguments: Sequence[str] | None = None) -> None:
    """
    Run the selected parser and write ModelRegistry.serialize() to the output file.

    Args:
        arguments: Command line arguments; sys.argv[1:] if None.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parser", required=True, choices=sorted(PARSERS))
    parser.add_argument("--src", action="append", required=True, type=Path, help="Root input file")
    parser.add_argument("--dep", action="append", default=[], type=Path, help="Input file the roots may import")
    parser.add_argument("--output", required=True, type=Path, help="Partial model file to write")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parsed = parser.parse_args(arguments)

    logging.basicConfig(level=parsed.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    PARSERS[parsed.parser](ParsingPathInfo(src_files=tuple(parsed.src), dependency_files=tuple(parsed.dep))).run()
    parsed.output.write_bytes(ModelRegistry.serialize())


if __name__ == "__main__":
    main()
