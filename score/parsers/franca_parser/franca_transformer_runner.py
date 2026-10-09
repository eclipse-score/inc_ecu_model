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

"""Bazel runner for the initial Franca FIDL transformer target."""

import argparse
import pickle
from pathlib import Path

from score.parsers.franca_parser.model.fidl.fidl_file import (
    FIDLFileModel,
)
from score.parsers.franca_parser.parser import FrancaParser
from score.parsers.franca_parser.transformer.file_graph_transformer import (
    FrancaFileGraphTransformer,
)


def main() -> None:
    """Transform Franca files and write the initial pickle contract."""
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--src", action="append", required=True)
    argument_parser.add_argument("--dep", action="append", default=[])
    argument_parser.add_argument("--out", required=True)
    argument_parser.add_argument("--defined", action="append", default=[])
    argument_parser.add_argument("--need_preprocessor", action="store_true", default=False)
    arguments = argument_parser.parse_args()

    parser = FrancaParser(
        root_files=[Path(source) for source in arguments.src],
        dependency_files=[Path(dependency) for dependency in arguments.dep],
        defined=arguments.defined,
        need_preprocessor=arguments.need_preprocessor,
    )
    transformed_files = FrancaFileGraphTransformer(parser.parse_files()).transform_files()
    datatypes = {}
    for file_model in transformed_files.values():
        if isinstance(file_model, FIDLFileModel):
            datatypes.update(file_model._datatype_index)
    with Path(arguments.out).open("wb") as output_file:
        pickle.dump({"datatypes": datatypes}, output_file)


if __name__ == "__main__":
    main()
