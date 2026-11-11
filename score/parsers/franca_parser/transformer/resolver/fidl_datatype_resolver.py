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
    FrancaTransformationContext,
)
from score.parsers.franca_parser.transformer.resolver.utils_resolver import (
    expand_fqn_candidates,
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

    def resolve(
        self,
        reference: QualifiedName,
        owning_file: FIDLFileModel,
        owning_collection: TypeCollection | InterfaceDefinition,
    ) -> DataTypeBase:
        """Resolve by owning scope, same-file type collections, then direct imports."""
        resolved = self.resolve_local(reference, owning_file, owning_collection)
        if resolved is not None:
            return resolved
        resolved = self.resolve_imports(reference, owning_file)
        if resolved is not None:
            return resolved
        raise ValueError(f"Referenced datatype '{reference.as_str}' in '{owning_file.file_path}' was not found")

    def resolve_local(
        self,
        reference: QualifiedName,
        owning_file: FIDLFileModel,
        owning_collection: TypeCollection | InterfaceDefinition,
    ) -> DataTypeBase | None:
        """Resolve the owning scope first, then other declarations in the same file."""
        return self._single_match(
            reference,
            owning_file,
            self._local_matches(reference, owning_file, owning_collection),
            required=False,
        )

    def resolve_imports(
        self,
        reference: QualifiedName,
        owning_file: FIDLFileModel | FrancaTransformationContext,
    ) -> DataTypeBase | None:
        """Resolve only a declaration in an imported FIDL file."""
        return self._single_match(
            reference,
            owning_file,
            self._import_matches(reference, owning_file),
            required=False,
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
        base_parts: tuple[str, ...] | None = None,
    ) -> list[DataTypeBase]:
        """Match names only against one scope, optionally allowing an unqualified name."""
        reference_qn_tuple = self._fqn_parts(reference)
        if len(reference_qn_tuple) == 1 and not allow_short_name:
            return []

        collection_fqn_tuple = self._fqn_parts(file_model.namespace)
        if collection.name is not None:
            collection_fqn_tuple = (*collection_fqn_tuple, collection.name.as_str)
        lookup_base_parts = base_parts or collection_fqn_tuple
        candidate_identities = set(expand_fqn_candidates(lookup_base_parts, reference_qn_tuple))
        return [
            datatype
            for datatype in collection.datatypes
            if ".".join((*collection_fqn_tuple, datatype.name.as_str)) in candidate_identities
        ]

    def _import_matches(
        self,
        reference: QualifiedName,
        owning_file: FIDLFileModel | FrancaTransformationContext,
    ) -> list[DataTypeBase]:
        matches: list[DataTypeBase] = []
        for imported_namespace in owning_file.imported_files:
            imported_file = self._files.get(imported_namespace.file_path)
            if not isinstance(imported_file, FIDLFileModel):
                continue
            base_parts = (
                self._fqn_parts(imported_namespace.namespace)
                if imported_namespace.namespace is not None
                else self._fqn_parts(imported_file.namespace)
            )
            for collection in imported_file.type_collections:
                matches.extend(
                    self._collection_matches(
                        imported_file,
                        collection,
                        reference,
                        allow_short_name=collection.name is None,
                        base_parts=base_parts,
                    )
                )
        return matches

    @staticmethod
    def _single_match(
        reference: QualifiedName,
        owning_file: FIDLFileModel | FrancaTransformationContext,
        matches: list[DataTypeBase],
        required: bool,
    ) -> DataTypeBase | None:
        distinct_matches: list[DataTypeBase] = []
        seen_declarations: set[int] = set()
        for match in matches:
            if id(match) not in seen_declarations:
                distinct_matches.append(match)
                seen_declarations.add(id(match))
        if len(distinct_matches) == 1:
            return distinct_matches[0]
        if not distinct_matches:
            if required:
                raise ValueError(f"Referenced datatype '{reference.as_str}' in '{owning_file.file_path}' was not found")
            return None
        raise ValueError(f"Ambiguous datatype reference '{reference.as_str}' in '{owning_file.file_path}'")

    @staticmethod
    def _fqn_parts(qualified_name: QualifiedName | None) -> tuple[str, ...]:
        return tuple(name.as_str for name in qualified_name.names) if qualified_name else ()
