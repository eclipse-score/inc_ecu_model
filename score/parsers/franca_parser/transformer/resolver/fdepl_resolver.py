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

"""Resolve FDEPL references against transformed Franca file models."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from score.ecu_model.common.common_name_types import QualifiedName
from score.parsers.franca_parser.model.fdepl.fdepl_file import (
    FDEPLFileModel,
)
from score.parsers.franca_parser.model.fdepl.specification import (
    DeploymentSpecification,
)
from score.parsers.franca_parser.model.fdepl.type_collection_deployment import (
    EnumValueDeployment,
    EnumerationDeployment,
    StructDeployment,
    TypeCollectionDeployment,
    TypeCollectionDatatypeDeployment,
    UnionDeployment,
)
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
    matches_use_definition_reference,
)


@dataclass
class PendingUseDefinition:
    """An unresolved use reference in one type-collection deployment."""

    reference: QualifiedName
    deployment: TypeCollectionDeployment
    index: int
    owning_file: FDEPLFileModel


class FDEPLResolver:
    """Resolve FDEPL specification and type-collection deployment references."""

    def __init__(self, files: Mapping[Path, FrancaFileModel]) -> None:
        """Create a resolver over the transformed Franca file graph."""
        self._files = files

    def resolve_base_specification(
        self,
        reference: QualifiedName,
        owning_file: FDEPLFileModel,
    ) -> DeploymentSpecification:
        """Resolve a specification declared locally or in transformed FDEPL imports."""
        for local_specification in owning_file.specifications:
            if local_specification.name == reference:
                return local_specification
        for imported_file in self._files.values():
            if not isinstance(imported_file, FDEPLFileModel):
                continue
            namespace_length = 0 if imported_file.namespace is None else len(imported_file.namespace.names)
            local_specification_name = (
                reference if len(reference.names) == 1 else QualifiedName(names=reference.names[namespace_length:])
            )
            for imported_specification in imported_file.specifications:
                if imported_specification.name == local_specification_name:
                    return imported_specification
        raise ValueError(
            f"Could not resolve deployment base specification {reference.as_str} in {owning_file.file_path}"
        )

    def resolve_type_collection(
        self,
        reference: QualifiedName,
        owning_file: FDEPLFileModel,
    ) -> TypeCollection:
        """Resolve one imported FIDL type collection or raise a contextual error."""
        matches: list[TypeCollection] = []
        for imported_namespace in owning_file.imported_files:
            imported_file = self._files.get(imported_namespace.file_path)
            if not isinstance(imported_file, FIDLFileModel) or imported_file.namespace is None:
                continue
            namespace = imported_file.namespace.names
            if reference.names[: len(namespace)] != namespace:
                continue
            for type_collection in imported_file.type_collections:
                if (
                    type_collection.name is None and reference.names == namespace
                ) or type_collection.name == reference.names[-1]:
                    matches.append(type_collection)
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ValueError(f"Could not resolve FIDL type collection {reference.as_str} in {owning_file.file_path}")
        raise ValueError(f"Ambiguous FIDL type collection {reference.as_str} in {owning_file.file_path}")

    def resolve_datatype_deployments(
        self,
        deployment: TypeCollectionDeployment,
        owning_file: FDEPLFileModel,
    ) -> None:
        """Resolve datatype and child deployments to their FIDL declarations."""
        for deployment_element in deployment.deployment_elements:
            self._resolve_datatype(
                deployment_element,
                deployment.target,
                owning_file,
            )

    def _resolve_use_definition(
        self,
        reference: QualifiedName,
        owning_file: FDEPLFileModel,
    ) -> TypeCollectionDeployment | None:
        """Resolve a local or transformed-import use reference when visible."""
        matches = [
            deployment
            for deployment in owning_file.type_collection_deployments
            if deployment.name is not None
            and matches_use_definition_reference(
                reference,
                deployment.name,
                owning_file.namespace,
            )
        ]
        for imported_namespace in owning_file.imported_files:
            imported_file = self._files.get(imported_namespace.file_path)
            if isinstance(imported_file, FDEPLFileModel):
                matches.extend(
                    [
                        deployment
                        for deployment in imported_file.type_collection_deployments
                        if deployment.name is not None
                        and matches_use_definition_reference(
                            reference,
                            deployment.name,
                            imported_file.namespace,
                            imported_namespace.namespace,
                        )
                    ]
                )
        distinct_matches = list({id(match): match for match in matches}.values())
        if len(distinct_matches) == 1:
            return distinct_matches[0]
        if not distinct_matches:
            return None
        raise ValueError(f"Ambiguous FDEPL use definition {reference.as_str} in {owning_file.file_path}")

    def resolve_use_definitions(
        self,
        deployment: TypeCollectionDeployment,
        owning_file: FDEPLFileModel,
    ) -> list[PendingUseDefinition]:
        """Resolve visible use references and return only circular-import candidates."""
        pending_references: list[PendingUseDefinition] = []
        resolver = FDEPLResolver({**self._files, owning_file.file_path: owning_file})
        for index, reference in enumerate(deployment.use_definitions):
            if not isinstance(reference, QualifiedName):
                continue
            resolved = resolver._resolve_use_definition(reference, owning_file)
            if resolved is None:
                pending_references.append(PendingUseDefinition(reference, deployment, index, owning_file))
            else:
                deployment.use_definitions[index] = resolved
        return pending_references

    def resolve_pending_use_definitions(
        self,
        pending_references: list[PendingUseDefinition],
    ) -> None:
        """Resolve use references deferred behind circular FDEPL imports."""
        for pending in pending_references:
            resolved = self._resolve_use_definition(
                pending.reference,
                pending.owning_file,
            )
            if resolved is None:
                raise ValueError(
                    f"Could not resolve FDEPL use definition {pending.reference.as_str} "
                    f"in {pending.owning_file.file_path}"
                )
            pending.deployment.use_definitions[pending.index] = resolved

    @staticmethod
    def _resolve_datatype(
        deployment_element: TypeCollectionDatatypeDeployment,
        type_collection: TypeCollection,
        owning_file: FDEPLFileModel,
    ) -> None:
        """Resolve one datatype deployment and any deployed members."""
        reference = deployment_element.deployed_type
        for datatype in type_collection.datatypes:
            if getattr(datatype, "name", None) == reference:
                break
        else:
            raise ValueError(f"Could not resolve FIDL datatype {reference.as_str} in {owning_file.file_path}")
        deployment_element.deployed_type = datatype
        if isinstance(deployment_element, EnumerationDeployment):
            FDEPLResolver._resolve_deployment_targets(
                deployment_element.enumerators,
                getattr(datatype, "values", []),
                "enumeration value",
                owning_file,
            )
        if not isinstance(deployment_element, (StructDeployment, UnionDeployment)):
            return
        FDEPLResolver._resolve_deployment_targets(
            deployment_element.fields,
            getattr(datatype, "fields", []),
            "field",
            owning_file,
        )

    @staticmethod
    def _resolve_deployment_targets(
        deployments: list[EnumValueDeployment] | list[object],
        targets: list[object],
        target_kind: str,
        owning_file: FDEPLFileModel,
    ) -> None:
        targets_by_name = {
            target.name.as_str: target for target in targets if getattr(target, "name", None) is not None
        }
        for deployment in deployments:
            target_name = deployment.deployed_type.as_str
            target = targets_by_name.get(target_name)
            if target is None:
                raise ValueError(f"Could not resolve FIDL {target_kind} {target_name} in {owning_file.file_path}")
            deployment.deployed_type = target
