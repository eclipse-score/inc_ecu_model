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

from collections.abc import Mapping
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from score.ecu_model.common.common_name_types import QualifiedName
from score.ecu_model.data_types.data_type_definition import (
    DataTypeDefinition,
    DataTypeModel,
)
from score.parsers.franca_parser.model.fidl.fidl_file import (
    FIDLFileModel,
)
from score.parsers.franca_parser.model.franca_file import (
    FrancaFileModel,
    FrancaTransformationContext,
)
from score.parsers.franca_parser.model.fidl.type_collection import (
    TypeCollection,
)
from score.parsers.franca_parser.transformer.resolver.utils_resolver import (
    expand_fqn_candidates,
)


@dataclass
class PendingDatatypeReference:
    """A typed FIDL reference slot awaiting declaration resolution."""

    reference: QualifiedName
    bind: Callable[[DataTypeDefinition], None]
    owning_declaration: DataTypeModel
    owning_file: FIDLFileModel | None = None
    owning_collection: TypeCollection | None = None


class FIDLDataTypeResolver:
    """Resolve FIDL datatype names while preserving type collection semantics."""

    def __init__(self, files: Mapping[Path, FrancaFileModel]) -> None:
        """Resolve FIDL datatype references against a transformed Franca file graph."""
        self._files = files

    def resolve(
        self,
        reference: QualifiedName,
        owning_file: FIDLFileModel,
        owning_collection: TypeCollection,
    ) -> DataTypeDefinition:
        """Resolve one reference from a type collection or raise a contextual error."""
        matches = self._local_matches(reference, owning_file, owning_collection)
        matches.extend(self._import_matches(reference, owning_file))
        return self._single_match(reference, owning_file, matches, required=True)

    def resolve_local(
        self,
        reference: QualifiedName,
        owning_file: FIDLFileModel,
        owning_collection: TypeCollection,
    ) -> DataTypeDefinition | None:
        """Resolve only a declaration in the owning type collection."""
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
    ) -> DataTypeDefinition | None:
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
        """Resolve datatype references deferred behind circular FIDL imports."""
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
        owning_collection: TypeCollection,
    ) -> list[DataTypeDefinition]:
        matches = self._lookup_candidates(
            owning_file, self._collection_base_parts(owning_file, owning_collection), reference
        )
        reference_parts = self._fqn_parts(reference)
        if len(reference_parts) > 1:
            sibling_identity = ".".join((*self._fqn_parts(owning_file.namespace), *reference_parts[-2:]))
            sibling = owning_file.lookup_datatype(sibling_identity)
            if sibling is not None:
                matches.append(sibling)
        return matches

    def _import_matches(
        self,
        reference: QualifiedName,
        owning_file: FIDLFileModel | FrancaTransformationContext,
    ) -> list[DataTypeDefinition]:
        matches: list[DataTypeDefinition] = []
        for imported_namespace in owning_file.imported_files:
            imported_file = self._files.get(imported_namespace.file_path)
            if not isinstance(imported_file, FIDLFileModel):
                continue
            base_parts = (
                self._fqn_parts(imported_namespace.namespace)
                if imported_namespace.namespace is not None
                else self._fqn_parts(imported_file.namespace)
            )
            matches.extend(self._lookup_candidates(imported_file, base_parts, reference))
        return matches

    @staticmethod
    def _single_match(
        reference: QualifiedName,
        owning_file: FIDLFileModel | FrancaTransformationContext,
        matches: list[DataTypeDefinition],
        required: bool,
    ) -> DataTypeDefinition | None:
        distinct_matches: list[DataTypeDefinition] = []
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

    def _lookup_candidates(
        self,
        target_file: FIDLFileModel,
        base_parts: tuple[str, ...],
        reference: QualifiedName,
    ) -> list[DataTypeDefinition]:
        return [
            datatype
            for candidate in expand_fqn_candidates(base_parts, self._fqn_parts(reference))
            if (datatype := target_file.lookup_datatype(candidate)) is not None
        ]

    def _collection_base_parts(self, file_model: FIDLFileModel, type_collection: TypeCollection) -> tuple[str, ...]:
        package_parts = self._fqn_parts(file_model.namespace)
        if type_collection.name is None:
            return package_parts
        return (*package_parts, type_collection.name.as_str)

    @staticmethod
    def _fqn_parts(qualified_name: QualifiedName | None) -> tuple[str, ...]:
        return tuple(name.as_str for name in qualified_name.names) if qualified_name else ()
