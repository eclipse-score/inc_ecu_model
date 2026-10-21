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

"""Import-first transformation over a graph of parsed Franca source files."""

from score.parsers.franca_parser.model.franca_file import (
    FrancaFileModel,
    FrancaTransformationContext,
)
from score.parsers.franca_parser.model.parsed_file import ParsedFile
from score.parsers.franca_parser.transformer.fdepl_transformer import (
    FDEPLTransformer,
)
from score.parsers.franca_parser.transformer.fidl_transformer import (
    FIDLTransformer,
)
from score.parsers.franca_parser.transformer.resolver.fdepl_resolver import (
    FDEPLResolver,
    PendingUseDefinition,
)
from score.parsers.franca_parser.transformer.resolver.fidl_datatype_resolver import (
    FIDLDataTypeResolver,
    PendingDatatypeReference,
)


class FrancaFileGraphTransformer:
    """Transform parsed Franca source files in import-first order."""

    def __init__(self, parsed_files: dict[object, ParsedFile]) -> None:
        self._parsed_files = parsed_files
        self._transformed_files: dict[object, FrancaFileModel] = {}
        # Files on the current DFS path, used to stop circular imports.
        self._visiting_files: set[object] = set()
        # References deferred until all imported files have been transformed.
        self._pending_datatype_references: list[PendingDatatypeReference] = []
        self._pending_use_definitions: list[PendingUseDefinition] = []

    @property
    def transformed_files(self) -> dict[object, FrancaFileModel]:
        """Return transformed file models indexed by source path."""
        return self._transformed_files

    def transform_files(self) -> None:
        """Transform all the Franca files, resolve deferred references, and validate interfaces. Entry point of this
        class."""
        # Transform parsed trees to models
        for file_path in self._parsed_files:
            self._process_file(file_path)

        # Resolve deferred references
        if self._pending_datatype_references:
            resolver = FIDLDataTypeResolver(self._transformed_files)
            resolver.resolve_pending_imports(self._pending_datatype_references)
        if self._pending_use_definitions:
            resolver = FDEPLResolver(self._transformed_files)
            resolver.resolve_pending_use_definitions(self._pending_use_definitions)

    def _process_file(self, file_path: object) -> None:
        """Transform one Franca file from parsed tree to model.

        More files might be processed recursively due to imports.

        :returns: This method returns None. However, the transformed file model is written to `self._transformed_files`.
        """
        # 1. Handle the recursive processing
        # A Franca file may import other files, which need to be processed first. The following code lines handle this
        # recursive processing.
        if file_path in self._transformed_files or file_path in self._visiting_files:
            return
        self._visiting_files.add(file_path)
        parsed_file = self._parsed_files[file_path]
        for imported_file in parsed_file.imports:
            self._process_file(imported_file.file_path)

        # 2. Process the current file
        # Provides import context while this file's declarations are transformed.
        transformation_context = FrancaTransformationContext(
            file_path=parsed_file.file_path,
            imported_files=parsed_file.imports,
        )
        if parsed_file.file_path.suffix == ".fidl":
            transformer = FIDLTransformer(self._transformed_files, transformation_context)
            file_model = transformer.transform_file(parsed_file)
            self._pending_datatype_references.extend(transformer.pending_datatype_references)
        elif parsed_file.file_path.suffix == ".fdepl":
            transformer = FDEPLTransformer(
                self._transformed_files,
                transformation_context,
            )
            file_model = transformer.transform_file(parsed_file)
            self._pending_use_definitions.extend(transformer.pending_use_definitions)
        else:
            raise ValueError(f"Unsupported Franca source type: {parsed_file.file_path}")
        self._transformed_files[file_path] = file_model
        self._visiting_files.remove(file_path)
