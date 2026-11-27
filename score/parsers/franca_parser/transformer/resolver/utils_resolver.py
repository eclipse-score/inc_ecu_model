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

"""Shared scoped lookup and qualified-name matching for Franca resolvers."""

from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Literal, TypeVar, overload

from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.parsers.franca_parser.model.franca_file import FrancaFileModel, ImportedNamespace

ElementType = TypeVar("ElementType")
FileType = TypeVar("FileType", bound=FrancaFileModel)
NameMatcher = Callable[[QualifiedName, QualifiedName | Identifier, QualifiedName | None, QualifiedName | None], bool]


def qualified_name_parts(qualified_name: QualifiedName | None) -> tuple[str, ...]:
    """Return identifier text, treating an absent namespace as the root scope."""
    return tuple(name.as_str for name in qualified_name.names) if qualified_name is not None else ()


def expand_fqn_candidates(base_parts: tuple[str, ...], reference_parts: tuple[str, ...]) -> tuple[str, ...]:
    """Return overlap-aware qualified-name candidates in deterministic order."""
    candidates: list[tuple[str, ...]] = []
    maximum_overlap = min(len(base_parts), len(reference_parts))
    for overlap_size in range(maximum_overlap, 0, -1):
        if base_parts[-overlap_size:] == reference_parts[:overlap_size]:
            candidates.append(base_parts + reference_parts[overlap_size:])
    candidates.append(base_parts + reference_parts)
    return tuple(dict.fromkeys(".".join(candidate) for candidate in candidates))


def is_namespace_visible(
    definition_namespace: QualifiedName | None,
    imported_namespace: QualifiedName | None,
) -> bool:
    """Return whether an import namespace exposes a definition namespace."""
    if imported_namespace is None or definition_namespace is None:
        return True
    return qualified_name_parts(definition_namespace)[: len(imported_namespace.names)] == qualified_name_parts(
        imported_namespace
    )


def matches_scoped_element_reference(
    reference: QualifiedName,
    element_name: QualifiedName | Identifier,
    definition_namespace: QualifiedName | None,
    imported_namespace: QualifiedName | None = None,
) -> bool:
    """Match an element identity against overlap-aware candidates from a lookup scope."""
    definition_parts = qualified_name_parts(definition_namespace)
    base_parts = qualified_name_parts(imported_namespace) or definition_parts
    candidates = expand_fqn_candidates(base_parts, qualified_name_parts(reference))
    return ".".join((*definition_parts, *_name_parts(element_name))) in candidates


def matches_named_element_reference(
    reference: QualifiedName,
    element_name: QualifiedName | Identifier,
    definition_namespace: QualifiedName | None,
    imported_namespace: QualifiedName | None = None,
) -> bool:
    """Match a reference to a namespace-qualified named Franca element."""
    if not is_namespace_visible(definition_namespace, imported_namespace):
        return False
    reference_prefix = qualified_name_parts(reference)[:-1]
    if reference_prefix and (
        definition_namespace is None
        or qualified_name_parts(definition_namespace)[-len(reference_prefix) :] != reference_prefix
    ):
        return False
    if imported_namespace is not None and len(reference_prefix) + len(imported_namespace.names) < len(
        definition_namespace.names if definition_namespace is not None else ()
    ):
        return False
    return _name_parts(element_name)[-1] == reference.names[-1].as_str


def matches_use_definition_reference(
    use_reference: QualifiedName,
    definition_name: QualifiedName,
    definition_namespace: QualifiedName | None,
    imported_namespace: QualifiedName | None = None,
) -> bool:
    """Match fd_tc/fd_interface. Special handling reason: name after 'as' is fd_fqn, not fd_valid_id"""
    if not is_namespace_visible(definition_namespace, imported_namespace):
        return False
    use_parts = qualified_name_parts(use_reference)
    definition_name_parts = qualified_name_parts(definition_name)
    if len(use_parts) < len(definition_name_parts) or use_parts[-len(definition_name_parts) :] != definition_name_parts:
        return False
    namespace_prefix = use_parts[: -len(definition_name_parts)]
    if namespace_prefix and (
        definition_namespace is None
        or qualified_name_parts(definition_namespace)[-len(namespace_prefix) :] != namespace_prefix
    ):
        return False
    return imported_namespace is None or len(namespace_prefix) + len(imported_namespace.names) >= len(
        definition_namespace.names if definition_namespace is not None else []
    )


def resolve_from_local(
    reference: QualifiedName,
    elements: Iterable[ElementType],
    definition_namespace: QualifiedName | None,
    name_of: Callable[[ElementType], QualifiedName | Identifier],
    *,
    imported_namespace: QualifiedName | None = None,
    matcher: NameMatcher = matches_named_element_reference,
) -> list[ElementType]:
    """Collect matches in one explicit scope without deciding scope precedence."""
    return [
        element
        for element in elements
        if matcher(reference, name_of(element), definition_namespace, imported_namespace)
    ]


def resolve_from_imported(
    reference: QualifiedName,
    imports: Iterable[ImportedNamespace],
    files: Mapping[Path, FrancaFileModel],
    file_type: type[FileType],
    find_matches: Callable[[QualifiedName, FileType, QualifiedName | None], Iterable[ElementType]],
) -> list[ElementType]:
    """Collect matches from direct imports while retaining each import's namespace."""
    matches: list[ElementType] = []
    for imported_namespace in imports:
        imported_file = files.get(imported_namespace.file_path)
        if isinstance(imported_file, file_type):
            matches.extend(find_matches(reference, imported_file, imported_namespace.namespace))
    return matches


@overload
def select_single_match(
    matches: Iterable[ElementType],
    *,
    not_found_message: str,
    ambiguous_message: str,
    required: Literal[True],
) -> ElementType: ...


@overload
def select_single_match(
    matches: Iterable[ElementType],
    *,
    not_found_message: str,
    ambiguous_message: str,
    required: Literal[False] = False,
) -> ElementType | None: ...


def select_single_match(
    matches: Iterable[ElementType],
    *,
    not_found_message: str,
    ambiguous_message: str,
    required: bool = False,
) -> ElementType | None:
    """Select one declaration by identity, allowing repeated imports of that declaration."""
    distinct_matches = list({id(match): match for match in matches}.values())
    if len(distinct_matches) == 1:
        return distinct_matches[0]
    if not distinct_matches:
        if required:
            raise ValueError(not_found_message)
        return None
    raise ValueError(ambiguous_message)


def _name_parts(name: QualifiedName | Identifier) -> tuple[str, ...]:
    """Return identifier text for a Franca name of either supported shape."""
    if isinstance(name, Identifier):
        return (name.as_str,)
    return qualified_name_parts(name)
