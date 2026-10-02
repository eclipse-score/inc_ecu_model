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

"""Example generator: list all datatypes of an ECU model pickle written by ecu_model_parse."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from score.ecu_model.model import ModelRegistry
from score.ecu_model.query import datatypes_by_name


def render() -> str:
    """Return one "<fully qualified name> <kind> <source>" line per named datatype, sorted by name."""
    datatypes = datatypes_by_name()
    return "".join(
        f"{name} {datatype.kind.value} {datatype.source_kind.value}\n" for name, datatype in sorted(datatypes.items())
    )


def main(arguments: Sequence[str] | None = None) -> None:
    """
    Load the model and write the datatype list.

    Args:
        arguments: Command line arguments; sys.argv[1:] if None.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path, help="Serialized ModelRegistry written by ecu_model_parse")
    parser.add_argument("--output", required=True, type=Path, help="Text file to write")
    parsed = parser.parse_args(arguments)

    ModelRegistry.deserialize(parsed.model.read_bytes())
    parsed.output.write_text(render())


if __name__ == "__main__":
    main()
