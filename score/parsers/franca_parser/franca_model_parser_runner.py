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

"""Bazel action entry point for parsing Franca inputs into model artifacts."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from score.parsers.franca_parser.parser import WrapperFrancaParser
from score.parsers.runner.common import ParsingPathInfo


def main(arguments: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", action="append", default=[])
    parser.add_argument("--dep", action="append", default=[])
    parser.add_argument("--registry-output", required=True)
    parsed_arguments = parser.parse_args(arguments)

    path_info = ParsingPathInfo(
        src_files=tuple(parsed_arguments.src),
        result_pickle_path=parsed_arguments.registry_output,
        ext_info={"dependency_files": tuple(parsed_arguments.dep)},
    )
    WrapperFrancaParser(path_info).parse()


if __name__ == "__main__":
    main()
