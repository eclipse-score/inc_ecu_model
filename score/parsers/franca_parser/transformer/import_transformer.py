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

"""Collect resolved FIDL imports from an already parsed Lark tree."""

from collections.abc import Callable
from pathlib import Path

from lark import v_args

from score.ecu_model.common.common_name_types import QualifiedName
from score.parsers.franca_parser.model.franca_file import (
    ImportedNamespace,
)
from score.parsers.franca_parser.transformer.base_transformer import (
    FrancaFileTransformer,
)


class FrancaImportTransformer(FrancaFileTransformer):
    """Extract import declarations and resolve their source paths."""

    def __init__(self, resolve_path: Callable[[str], Path]) -> None:
        super().__init__()
        self._resolve_path = resolve_path
        self.imported_namespaces: list[ImportedNamespace] = []

    @v_args(inline=True)
    def f_imports(self, *elements: QualifiedName | str) -> None:
        """Store one import declaration when it includes a source URI."""
        namespace = next((element for element in elements if isinstance(element, QualifiedName)), None)
        import_uri = next((element for element in elements if isinstance(element, str)), None)
        if import_uri is not None:
            self.imported_namespaces.append(
                ImportedNamespace(
                    file_path=self._resolve_path(import_uri),
                    namespace=namespace,
                    is_wildcard=namespace is not None,
                )
            )

    @staticmethod
    @v_args(inline=True)
    def f_import_uri(uri: object) -> str:
        """Normalize quoted Franca import URIs."""
        return str(uri).strip("'\"")
