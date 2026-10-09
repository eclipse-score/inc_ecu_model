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

"""Parsed Franca source file model."""

from dataclasses import dataclass, field
from pathlib import Path

from lark import Tree

from score.parsers.franca_parser.model.franca_file import ImportedNamespace


@dataclass
class ParsedFile:
    """Represent a parsed Franca file, its syntax tree, and its imported namespaces."""

    file_path: Path
    parse_tree: Tree
    imports: list[ImportedNamespace] = field(default_factory=list)
