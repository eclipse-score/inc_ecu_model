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

"""Load a trusted ECU-model pickle and invoke registered code generators."""

import argparse
import pickle
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol
from uuid import UUID

from score.ecu_model.model import ModelElement
from score.generators.src.datatypes.datatype_generator import DatatypeGenerator


class Generator(Protocol):
    """Common interface for generators sharing an input model and output root."""

    def generate(self, model: Mapping[str, Mapping[UUID, ModelElement]], output_dir: Path) -> None:
        """Write generated artifacts below the supplied output root."""
        ...  # pragma: no cover


GENERATOR_FACTORIES: tuple[type[Generator], ...] = (DatatypeGenerator,)


class GeneratorRunner:
    """Coordinate model loading and sequential generator invocation."""

    def run(self, input_path: Path, output_dir: Path) -> None:
        """Load the model once and stop on the first loading or generation error."""
        model = pickle.loads(input_path.read_bytes())

        output_dir.mkdir(parents=True, exist_ok=True)
        for factory in GENERATOR_FACTORIES:
            generator = factory()
            try:
                generator.generate(model, output_dir)
            except Exception as error:
                raise RuntimeError(f"{type(generator).__name__} generation failed") from error


def main() -> None:
    """Parse Bazel-supplied paths and invoke the generator runner."""
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument("--input", type=Path, required=True)
    argument_parser.add_argument("--output-dir", type=Path, required=True)
    arguments = argument_parser.parse_args()
    GeneratorRunner().run(arguments.input, arguments.output_dir)


if __name__ == "__main__":
    main()
