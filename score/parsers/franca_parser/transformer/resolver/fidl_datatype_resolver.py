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

"""Resolve FIDL datatype references against local and imported type collections."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from score.ecu_model.communication.service_interface import InterfaceDefinition
from score.ecu_model.data_types.common import DataTypeBase
from score.ecu_model.data_types.identifier import QualifiedName
from score.ecu_model.model import ModelElement
from score.parsers.franca_parser.model.fidl.fidl_file import (
    FIDLFileModel,
)
from score.parsers.franca_parser.model.fidl.type_collection import (
    TypeCollection,
)
from score.parsers.franca_parser.model.franca_file import (
    FrancaFileModel,
)
from score.parsers.franca_parser.transformer.resolver.utils_resolver import (
    matches_scoped_element_reference,
    resolve_from_imported,
    resolve_from_local,
    select_single_match,
)


@dataclass
class PendingDatatypeReference:
    """A typed FIDL reference slot awaiting declaration resolution."""

    reference: QualifiedName
    bind: Callable[[DataTypeBase], None]
    owning_declaration: ModelElement
    owning_file: FIDLFileModel | None = None
    owning_collection: TypeCollection | InterfaceDefinition | None = None


class FIDLDataTypeResolver:
    """Resolve FIDL datatype names while preserving type collection semantics."""

    def __init__(self, files: Mapping[Path, FrancaFileModel]) -> None:
        """Resolve FIDL datatype references against a transformed Franca file graph."""
        self._files = files

    def resolve_local(
        self,
        reference: QualifiedName,
        owning_file: FIDLFileModel,
        owning_collection: TypeCollection | InterfaceDefinition,
    ) -> DataTypeBase | None:
        """Resolve the owning scope first, then other declarations in the same file."""
        return select_single_match(
            self._local_matches(reference, owning_file, owning_collection),
            not_found_message=f"Referenced datatype '{reference.as_str}' in '{owning_file.file_path}' was not found",
            ambiguous_message=f"Ambiguous datatype reference '{reference.as_str}' in '{owning_file.file_path}'",
        )

    def resolve_imports(
        self,
        reference: QualifiedName,
        owning_file: FIDLFileModel,
    ) -> DataTypeBase | None:
        """Resolve only a declaration in an imported FIDL file."""
        return select_single_match(
            resolve_from_imported(
                reference, owning_file.imported_files, self._files, FIDLFileModel, self._import_matches
            ),
            not_found_message=f"Referenced datatype '{reference.as_str}' in '{owning_file.file_path}' was not found",
            ambiguous_message=f"Ambiguous datatype reference '{reference.as_str}' in '{owning_file.file_path}'",
        )

    def resolve_local_references(
        self,
        pending_references: list[PendingDatatypeReference],
        owning_file: FIDLFileModel,
    ) -> list[PendingDatatypeReference]:
        """Bind local references and return only circular-import candidates."""
        unresolved_references: list[PendingDatatypeReference] = []
        for pending in pending_references:
            pending.owning_file = owning_file
            resolved = self.resolve_local(
                pending.reference,
                owning_file,
                pending.owning_collection,
            )
            if resolved is None:
                unresolved_references.append(pending)
            else:
                pending.bind(resolved)
        return unresolved_references

    def resolve_pending_imports(
        self,
        pending_references: list[PendingDatatypeReference],
    ) -> None:
        """Resolve references deferred until every imported FIDL file is transformed."""
        for pending in pending_references:
            if pending.owning_file is None:
                raise ValueError(f"Missing owning FIDL file for datatype reference {pending.reference.as_str}")
            resolved = self.resolve_imports(pending.reference, pending.owning_file)
            if resolved is None:
                raise ValueError(
                    f"Referenced datatype '{pending.reference.as_str}' "
                    f"in '{pending.owning_file.file_path}' was not found"
                )
            pending.bind(resolved)

    def _local_matches(
        self,
        reference: QualifiedName,
        owning_file: FIDLFileModel,
        owning_collection: TypeCollection | InterfaceDefinition,
    ) -> list[DataTypeBase]:
        matches = self._collection_matches(owning_file, owning_collection, reference, allow_short_name=True)
        if matches:
            return matches

        matches = []
        for collection in owning_file.type_collections:
            if isinstance(owning_collection, TypeCollection) and collection is owning_collection:
                continue
            matches.extend(
                self._collection_matches(
                    owning_file,
                    collection,
                    reference,
                    allow_short_name=collection.name is None,
                )
            )
        return matches

    def _collection_matches(
        self,
        file_model: FIDLFileModel,
        collection: TypeCollection | InterfaceDefinition,
        reference: QualifiedName,
        allow_short_name: bool,
        lookup_namespace: QualifiedName | None = None,
    ) -> list[DataTypeBase]:
        """Match names only against one scope, optionally allowing an unqualified name."""
        if len(reference.names) == 1 and not allow_short_name:
            return []

        namespace_names = tuple(file_model.namespace.names) if file_model.namespace is not None else ()
        if collection.name is not None:
            namespace_names = (*namespace_names, collection.name)
        return resolve_from_local(
            reference,
            collection.datatypes,
            QualifiedName(namespace_names) if namespace_names else None,
            lambda datatype: datatype.name,
            imported_namespace=lookup_namespace,
            matcher=matches_scoped_element_reference,
        )

    def _import_matches(
        self,
        reference: QualifiedName,
        imported_file: FIDLFileModel,
        imported_namespace: QualifiedName | None,
    ) -> list[DataTypeBase]:
        matches: list[DataTypeBase] = []
        lookup_namespace = imported_namespace if imported_namespace is not None else imported_file.namespace
        for collection in imported_file.type_collections:
            matches.extend(
                self._collection_matches(
                    imported_file,
                    collection,
                    reference,
                    allow_short_name=collection.name is None,
                    lookup_namespace=lookup_namespace,
                )
            )
        return matches
