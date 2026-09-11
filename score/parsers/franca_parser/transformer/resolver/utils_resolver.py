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

"""Shared qualified-name matching utilities for Franca resolvers."""

from score.ecu_model.common.common_name_types import Identifier, QualifiedName


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
    return _parts(definition_namespace)[: len(imported_namespace.names)] == _parts(imported_namespace)


def matches_named_element_reference(
    reference: QualifiedName,
    element_name: QualifiedName | Identifier,
    definition_namespace: QualifiedName | None,
    imported_namespace: QualifiedName | None = None,
) -> bool:
    """Match a reference to a namespace-qualified named Franca element."""
    if not is_namespace_visible(definition_namespace, imported_namespace):
        return False
    reference_prefix = _parts(reference)[:-1]
    if reference_prefix and (
        definition_namespace is None or _parts(definition_namespace)[-len(reference_prefix) :] != reference_prefix
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
    use_parts = _parts(use_reference)
    definition_name_parts = _parts(definition_name)
    if len(use_parts) < len(definition_name_parts) or use_parts[-len(definition_name_parts) :] != definition_name_parts:
        return False
    namespace_prefix = use_parts[: -len(definition_name_parts)]
    if namespace_prefix and (
        definition_namespace is None or _parts(definition_namespace)[-len(namespace_prefix) :] != namespace_prefix
    ):
        return False
    return imported_namespace is None or len(namespace_prefix) + len(imported_namespace.names) >= len(
        definition_namespace.names if definition_namespace is not None else []
    )


def _parts(qualified_name: QualifiedName) -> tuple[str, ...]:
    """Return identifier text for qualified-name matching."""
    return tuple(name.as_str for name in qualified_name.names)


def _name_parts(name: QualifiedName | Identifier) -> tuple[str, ...]:
    """Return identifier text for a Franca name of either supported shape."""
    if isinstance(name, Identifier):
        return (name.as_str,)
    return _parts(name)
